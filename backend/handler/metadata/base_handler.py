import abc
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Final, Mapping, NotRequired, TypedDict
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import HTTPException, status
from strsimpy.jaro_winkler import JaroWinkler

from handler.redis_handler import async_cache
from logger.logger import log
from tasks.scheduled.update_switch_titledb import (
    SWITCH_PRODUCT_ID_KEY,
    SWITCH_TITLEDB_INDEX_KEY,
)
from utils.context import ctx_httpx_client
from utils.switch import derive_base_title_id

if TYPE_CHECKING:
    from models.rom import Rom

jarowinkler = JaroWinkler()

METADATA_FIXTURES_DIR: Final = Path(__file__).parent / "fixtures"

# Providers are third parties; a response is read only this far before it is dropped.
MAX_RESPONSE_BYTES: Final[int] = 1_000_000
REQUEST_TIMEOUT: Final[int] = 25

# These are loaded in cache in update_switch_titledb_task
SWITCH_TITLEDB_REGEX: Final = re.compile(r"(70[0-9]{12})")
SWITCH_PRODUCT_ID_REGEX: Final = re.compile(r"(0100[0-9A-F]{12})")


# No regex needed for MAME
MAME_XML_KEY: Final = "romm:mame_xml"

# ScummVM
SCUMMVM_INDEX_KEY: Final = "romm:scummvm_index"

# PS2 OPL
PS2_OPL_REGEX: Final = re.compile(r"^([A-Z]{4}_\d{3}\.\d{2})\..*$")
PS2_OPL_KEY: Final = "romm:ps2_opl_index"

# Sony serial codes for PS1, PS2, PS3 and PSP
SONY_SERIAL_REGEX: Final = re.compile(r".*([a-zA-Z]{4}-\d{5}).*$")

PS1_SERIAL_INDEX_KEY: Final = "romm:ps1_serial_index"
PS2_SERIAL_INDEX_KEY: Final = "romm:ps2_serial_index"
PSP_SERIAL_INDEX_KEY: Final = "romm:psp_serial_index"

LEADING_ARTICLE_PATTERN = re.compile(r"^(a|an|the)\b", re.IGNORECASE)
COMMA_ARTICLE_PATTERN = re.compile(r",\s(a|an|the)\b(?=\s*[^\w\s]|$)", re.IGNORECASE)
NON_WORD_SPACE_PATTERN = re.compile(r"[^\w\s]")
MULTIPLE_SPACE_PATTERN = re.compile(r"\s+")


def unavailable(provider: str) -> HTTPException:
    """The error a provider raises when it can't be reached."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Can't connect to {provider}, check your internet connection",
    )


class BaseRom(TypedDict):
    name: NotRequired[str]
    name_sort_key: NotRequired[str | None]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    url_manual: NotRequired[str]


SENSITIVE_KEYS = {
    "Authorization",
    "Client-ID",
    "Client-Secret",
    "client_id",
    "client_secret",
    "api_key",
    "ssid",
    "sspassword",
    "devid",
    "devpassword",
    "y",
}
SENSITIVE_KEYS_REGEX = re.compile(
    rf"({'|'.join(re.escape(k) for k in SENSITIVE_KEYS)})=[^&\s\"]*",
    re.IGNORECASE,
)


# This caches results to avoid repeated normalization of the same search term
@lru_cache(maxsize=1024)
def _normalize_search_term(
    name: str, remove_articles: bool = True, remove_punctuation: bool = True
) -> str:
    # Lower and replace underscores with spaces
    name = name.lower().replace("_", " ")

    # Remove articles (combined if possible)
    if remove_articles:
        name = LEADING_ARTICLE_PATTERN.sub("", name)
        name = COMMA_ARTICLE_PATTERN.sub("", name)

    # Remove punctuation and normalize spaces in one step
    if remove_punctuation:
        name = NON_WORD_SPACE_PATTERN.sub(" ", name)
        name = MULTIPLE_SPACE_PATTERN.sub(" ", name)

    # Unicode normalization and accent removal
    if any(ord(c) > 127 for c in name):  # Only if non-ASCII chars present
        normalized = unicodedata.normalize("NFD", name)
        name = "".join(c for c in normalized if not unicodedata.combining(c))

    return name.strip()


def strip_sensitive_query_params(
    url: str, sensitive_keys: set[str] = SENSITIVE_KEYS
) -> str:
    """Remove sensitive query parameters from a URL."""
    parsed = urlparse(url)
    qsl = parse_qsl(parsed.query, keep_blank_values=True)

    keys_lower = {k.lower() for k in sensitive_keys}
    keep = [(k, v) for k, v in qsl if k.lower() not in keys_lower]

    new_query = urlencode(keep, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def restore_sensitive_query_params(url: str, params: dict[str, str]) -> str:
    """Add back key/value pairs previously stripped by strip_sensitive_query_params."""
    parsed = urlparse(url)
    qsl = parse_qsl(parsed.query, keep_blank_values=True)

    existing = {k.lower() for k in params}
    filtered = [(k, v) for k, v in qsl if k.lower() not in existing]

    new_query = urlencode(filtered + list(params.items()))
    return urlunparse(parsed._replace(query=new_query))


class MetadataHandler(abc.ABC):
    SEARCH_TERM_SPLIT_PATTERN = re.compile(r"[\:\-\/]")
    SEARCH_TERM_NORMALIZER = re.compile(r"\s*[:-]\s+")

    @classmethod
    @abc.abstractmethod
    def is_enabled(cls) -> bool:
        """Return whether this metadata handler is enabled."""

    async def _fetch_capped(
        self, url: str, *, headers: Mapping[str, str]
    ) -> bytes | None:
        """Stream a body, returning None rather than reading past the cap."""
        httpx_client = ctx_httpx_client.get()
        body = bytearray()
        async with httpx_client.stream(
            "GET", url, headers=dict(headers), timeout=REQUEST_TIMEOUT
        ) as res:
            res.raise_for_status()
            async for chunk in res.aiter_bytes():
                body += chunk
                if len(body) > MAX_RESPONSE_BYTES:
                    log.warning(
                        "Response from %s exceeds %s bytes", url, MAX_RESPONSE_BYTES
                    )
                    return None
        return bytes(body)

    def normalize_cover_url(self, url: str) -> str:
        return url if not url else f"https:{url.replace('https:', '')}"

    def normalize_search_term(
        self, name: str, remove_articles: bool = True, remove_punctuation: bool = True
    ) -> str:
        return _normalize_search_term(name, remove_articles, remove_punctuation)

    def find_best_match(
        self,
        search_term: str,
        game_names: list[str],
        min_similarity_score: float = 0.75,
        split_game_name: bool = False,
    ) -> tuple[str | None, float]:
        """
        Find the best matching game name from a list of candidates.

        Args:
            search_term: The search term to match
            game_names: List of game names to check against
            min_similarity_score: Minimum similarity score to consider a match

        Returns:
            Tuple of (best_match_name, similarity_score) or (None, 0.0) if no good match
        """
        if not game_names:
            return None, 0.0

        best_match = None
        best_score = 0.0
        search_term_normalized = self.normalize_search_term(search_term)

        for game_name in game_names:
            game_name_normalized = self.normalize_search_term(game_name)

            # If the game name is split, normalize the last term
            if split_game_name and re.search(self.SEARCH_TERM_SPLIT_PATTERN, game_name):
                game_name_normalized = self.normalize_search_term(
                    re.split(self.SEARCH_TERM_SPLIT_PATTERN, game_name)[-1]
                )

            score = jarowinkler.similarity(search_term_normalized, game_name_normalized)
            if score > best_score:
                best_score = score
                best_match = game_name

                # Early exit for perfect match
                if score == 1.0:
                    break

        if best_score >= min_similarity_score:
            return best_match, best_score

        return None, 0.0

    async def _ps2_opl_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        index_entry = await async_cache.hget(PS2_OPL_KEY, serial_code)
        if index_entry:
            index_entry = json.loads(index_entry)
            search_term = index_entry["Name"]  # type: ignore

        return search_term

    async def _sony_serial_format(self, index_key: str, serial_code: str) -> str | None:
        index_entry = await async_cache.hget(index_key, serial_code.upper())
        if index_entry:
            index_entry = json.loads(index_entry)
            return index_entry["title"]

        return None

    async def _ps1_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return (
            await self._sony_serial_format(PS1_SERIAL_INDEX_KEY, serial_code)
            or search_term
        )

    async def _ps2_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return (
            await self._sony_serial_format(PS2_SERIAL_INDEX_KEY, serial_code)
            or search_term
        )

    async def _psp_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return (
            await self._sony_serial_format(PSP_SERIAL_INDEX_KEY, serial_code)
            or search_term
        )

    async def _switch_titledb_format(
        self, match: re.Match[str], search_term: str
    ) -> tuple[str, dict | None]:
        title_id = match.group(1)

        if not (await async_cache.exists(SWITCH_TITLEDB_INDEX_KEY)):
            log.error("Could not find the Switch titleID index file in cache")
            return search_term, None

        index_entry = await async_cache.hget(SWITCH_TITLEDB_INDEX_KEY, title_id)
        if index_entry:
            index_entry = json.loads(index_entry)
            return index_entry["name"], index_entry

        return search_term, None

    async def _switch_productid_format(
        self, rom: "Rom", fs_name: str, search_term: str
    ) -> tuple[str, dict | None]:
        """Match by Switch product id, preferring the one the scan read out of
        the binary over one scraped from the filename."""
        if rom.title_id and SWITCH_PRODUCT_ID_REGEX.fullmatch(rom.title_id.upper()):
            product_id = rom.title_id.upper()
        else:
            match = SWITCH_PRODUCT_ID_REGEX.search(fs_name)
            if not match:
                return search_term, None
            product_id = match.group(1)

        # Updates and DLC share the base application's product ID, off by the
        # low 12 bits, and only the base has a titledb entry.
        product_id = derive_base_title_id(product_id) or product_id

        if not (await async_cache.exists(SWITCH_PRODUCT_ID_KEY)):
            log.error("Could not find the Switch productID index file in cache")
            return search_term, None

        index_entry = await async_cache.hget(SWITCH_PRODUCT_ID_KEY, product_id)
        if index_entry:
            index_entry = json.loads(index_entry)
            return index_entry["name"], index_entry

        return search_term, None

    async def _mame_format(self, search_term: str) -> str:
        from handler.filesystem import fs_rom_handler

        index_entry = await async_cache.hget(MAME_XML_KEY, search_term)
        if index_entry:
            index_entry = json.loads(index_entry)
            search_term = fs_rom_handler.get_file_name_with_no_tags(
                index_entry.get("description", search_term)
            )

        return search_term

    async def _scummvm_format(self, search_term: str) -> str:
        from handler.filesystem import fs_rom_handler

        search_term = fs_rom_handler.get_file_name_with_no_extension(search_term)
        index_entry = await async_cache.hget(SCUMMVM_INDEX_KEY, search_term)
        if index_entry:
            index_entry = json.loads(index_entry)
            search_term = index_entry["name"]

        return search_term

    def _mask_sensitive_values(
        self, values: Mapping[str, str | None]
    ) -> dict[str, str]:
        """
        Mask sensitive values (headers or params), leaving only the first 2 and last 2 characters of the token.
        """
        masked_keys: dict[str, str] = {}
        for key, val in values.items():
            if val is None:
                masked_keys[key] = ""
                continue

            if key == "Authorization" and val.startswith("Bearer "):
                token = val.split(" ", 1)[1]
                masked_keys[key] = f"Bearer {token[:2]}***{token[-2:]}"
            elif key in SENSITIVE_KEYS:
                masked_keys[key] = f"{val[:2]}***{val[-2:]}"
            else:
                masked_keys[key] = val
        return masked_keys
