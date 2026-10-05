import abc
import json
import re
import unicodedata
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Mapping, NotRequired, TypedDict, cast
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx2
from strsimpy.jaro_winkler import JaroWinkler

from adapters.services.provider_http import unavailable
from handler.dump_cache import hget_json
from handler.redis_handler import async_cache
from logger.formatter import SENSITIVE_KEYS
from logger.logger import log
from tasks.scheduled.update_switch_titledb import (
    SWITCH_PRODUCT_ID_KEY,
    SWITCH_TITLEDB_INDEX_KEY,
    SWITCH_TITLEDB_STORE,
)
from utils import get_version, int_or_none
from utils.cache import is_cache_store_ready
from utils.context import ctx_httpx_client
from utils.switch import derive_base_title_id

if TYPE_CHECKING:
    from models.rom import Rom

jarowinkler = JaroWinkler()

METADATA_FIXTURES_DIR: Final = Path(__file__).parent / "fixtures"

# An error status, or a request that never got an answer.
HTTPX_REQUEST_ERRORS: Final = (httpx2.HTTPStatusError, httpx2.TransportError)

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


def provider_tag_regex(prefix: str) -> re.Pattern[str]:
    """The filename tag that pins a ROM to a provider id, like ``(igdb-1234)``."""
    return re.compile(rf"\({prefix}-(\d+)\)", re.IGNORECASE)


def tag_id_from_filename(tag_regex: re.Pattern[str], fs_name: str) -> int | None:
    match = tag_regex.search(fs_name)
    return int_or_none(match.group(1)) if match else None


class BaseRom(TypedDict):
    name: NotRequired[str]
    name_sort_key: NotRequired[str | None]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    url_manual: NotRequired[str]


@dataclass(frozen=True, slots=True)
class IndexedFormatPlatforms:
    """A provider's ids for the platforms whose filenames resolve through a local index."""

    ps1: int
    ps2: int
    psp: int
    switch: int
    arcade: Collection[int]
    scummvm: int | None = None


def _fill_from_switch_entry(fallback_rom: BaseRom, index_entry: dict[str, Any]) -> None:
    fallback_rom["name"] = index_entry["name"]
    fallback_rom["summary"] = index_entry.get("description", "")
    fallback_rom["url_cover"] = index_entry.get("iconUrl", "")
    fallback_rom["url_screenshots"] = index_entry.get("screenshots", None) or []


class CoverResource(TypedDict):
    """One piece of artwork the manual cover search offers, in the shape
    SteamGridDB grids have, so every provider fills the same picker."""

    thumb: str
    url: str
    type: str
    width: int
    height: int
    style: str
    author: str
    score: int
    nsfw: bool
    humor: bool
    epilepsy: bool


class CoverResult(TypedDict):
    name: str
    resources: list[CoverResource]


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

    async def _heartbeat(
        self, provider: str, probe: Callable[[], Awaitable[bool]]
    ) -> bool:
        """Whether the provider is enabled and answers `probe`.

        Args:
            probe: A cheap request; raising counts as the provider being down.
        """
        if not self.is_enabled():
            return False
        try:
            return await probe()
        except Exception as exc:
            log.error("Error checking %s: %s", provider, exc)
            return False

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

    async def _get_capped(
        self, url: str, *, provider: str, accept: str, missing_ok: bool = False
    ) -> bytes | None:
        """Fetch a provider URL under the size cap, raising a 503 when it fails.

        Args:
            missing_ok: Read a 404 as no answer rather than as the provider failing.
        """
        headers = {"User-Agent": f"RomM/{get_version()}", "Accept": accept}
        try:
            return await self._fetch_capped(url, headers=headers)
        except HTTPX_REQUEST_ERRORS as exc:
            if (
                missing_ok
                and isinstance(exc, httpx2.HTTPStatusError)
                and exc.response.status_code == httpx2.codes.NOT_FOUND
            ):
                return None
            log.warning("Can't connect to %s", provider, extra={"exception": str(exc)})
            raise unavailable(provider) from exc

    async def _get_capped_json(
        self, url: str, *, provider: str, missing_ok: bool = False
    ) -> dict[str, Any]:
        """Fetch a provider's JSON object, or an empty one when the reply isn't one."""
        body = await self._get_capped(
            url, provider=provider, accept="application/json", missing_ok=missing_ok
        )
        if body is None:
            return {}
        try:
            data = json.loads(body)
        except ValueError as exc:
            log.error("Error decoding JSON from %s: %s", provider, exc)
            return {}
        return data if isinstance(data, dict) else {}

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

    async def _resolve_indexed_title(
        self,
        rom: "Rom",
        fs_name: str,
        search_term: str,
        platform_id: int,
        platforms: IndexedFormatPlatforms,
        fallback_rom: BaseRom,
    ) -> str:
        """Swap a serial, title id or short name in the filename for the title its index holds.

        Args:
            fallback_rom: Filled with what the index knows, for when the provider finds no match.

        Returns:
            The term to search the provider for.
        """
        match = PS2_OPL_REGEX.match(fs_name)
        if platform_id == platforms.ps2 and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom["name"] = search_term

        match = SONY_SERIAL_REGEX.search(fs_name)
        if platform_id == platforms.ps1 and match:
            search_term = await self._ps1_serial_format(match, search_term)
            fallback_rom["name"] = search_term

        if platform_id == platforms.ps2 and match:
            search_term = await self._ps2_serial_format(match, search_term)
            fallback_rom["name"] = search_term

        if platform_id == platforms.psp and match:
            search_term = await self._psp_serial_format(match, search_term)
            fallback_rom["name"] = search_term

        if platform_id == platforms.switch:
            match = SWITCH_TITLEDB_REGEX.search(fs_name)
            if match:
                search_term, index_entry = await self._switch_titledb_format(
                    match, search_term
                )
                if index_entry:
                    _fill_from_switch_entry(fallback_rom, index_entry)

            search_term, index_entry = await self._switch_productid_format(
                rom, fs_name, search_term
            )
            if index_entry:
                _fill_from_switch_entry(fallback_rom, index_entry)

        if platform_id in platforms.arcade:
            search_term = await self._mame_format(search_term)
            fallback_rom["name"] = search_term

        if platforms.scummvm is not None and platform_id == platforms.scummvm:
            search_term = await self._scummvm_format(search_term)
            fallback_rom["name"] = search_term

        return search_term

    async def _ps2_opl_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        index_entry = await async_cache.hget(PS2_OPL_KEY, serial_code)
        if index_entry:
            index_entry = json.loads(index_entry)
            search_term = index_entry["Name"]

        return search_term

    async def _sony_serial_format(self, index_key: str, serial_code: str) -> str | None:
        index_entry = await async_cache.hget(index_key, serial_code.upper())
        if index_entry:
            index_entry = json.loads(index_entry)
            return cast(str | None, index_entry["title"])

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
    ) -> tuple[str, dict[str, Any] | None]:
        title_id = match.group(1)

        if not await self._is_switch_titledb_current():
            log.error("Could not find a current Switch titleID index in cache")
            return search_term, None

        index_entry = await self._switch_titledb_entry(title_id)
        if index_entry:
            return index_entry["name"], index_entry

        return search_term, None

    async def _switch_productid_format(
        self, rom: "Rom", fs_name: str, search_term: str
    ) -> tuple[str, dict[str, Any] | None]:
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

        if not await self._is_switch_titledb_current():
            log.error("Could not find a current Switch productID index in cache")
            return search_term, None

        index_entry = await self._switch_product_id_entry(product_id)
        if index_entry:
            return index_entry["name"], index_entry

        return search_term, None

    @staticmethod
    async def _is_switch_titledb_current() -> bool:
        """Whether the titleID index was written by the current import."""
        return await is_cache_store_ready(
            async_cache, SWITCH_TITLEDB_STORE, SWITCH_TITLEDB_INDEX_KEY
        )

    @staticmethod
    async def _switch_titledb_entry(title_id: str) -> dict[str, Any] | None:
        return cast(
            dict[str, Any] | None, await hget_json(SWITCH_TITLEDB_INDEX_KEY, title_id)
        )

    @classmethod
    async def _switch_product_id_entry(cls, product_id: str) -> dict[str, Any] | None:
        """Resolve a Switch product id to the titleID entry its index points at."""
        title_id = await hget_json(SWITCH_PRODUCT_ID_KEY, product_id)
        if not title_id:
            return None

        return await cls._switch_titledb_entry(title_id)

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
