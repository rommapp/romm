import json
import os
import re
import unicodedata
from functools import lru_cache
from itertools import batched
from typing import Final

from handler.redis_handler import async_cache, sync_cache
from logger.logger import log
from tasks.update_switch_titledb import (
    SWITCH_PRODUCT_ID_KEY,
    SWITCH_TITLEDB_INDEX_KEY,
    update_switch_titledb_task,
)


def conditionally_set_cache(
    index_key: str, filename: str, parent_dir: str = os.path.dirname(__file__)
) -> None:
    try:
        fixtures_path = os.path.join(parent_dir, "fixtures")
        if not sync_cache.exists(index_key):
            index_data = json.loads(open(os.path.join(fixtures_path, filename)).read())
            with sync_cache.pipeline() as pipe:
                for data_batch in batched(index_data.items(), 2000, strict=False):
                    data_map = {k: json.dumps(v) for k, v in dict(data_batch).items()}
                    pipe.hset(index_key, mapping=data_map)
                pipe.execute()
    except Exception as e:
        # Log the error but don't fail - this allows migrations to run even if Redis is not available
        log.warning(f"Failed to initialize cache for {index_key}: {e}")


# These are loaded in cache in update_switch_titledb_task
SWITCH_TITLEDB_REGEX: Final = re.compile(r"(70[0-9]{12})")
SWITCH_PRODUCT_ID_REGEX: Final = re.compile(r"(0100[0-9A-F]{12})")


# No regex needed for MAME
MAME_XML_KEY: Final = "romm:mame_xml"

# PS2 OPL
PS2_OPL_REGEX: Final = re.compile(r"^([A-Z]{4}_\d{3}\.\d{2})\..*$")
PS2_OPL_KEY: Final = "romm:ps2_opl_index"

# Sony serial codes for PS1, PS2, and PSP
SONY_SERIAL_REGEX: Final = re.compile(r".*([a-zA-Z]{4}-\d{5}).*$")

PS1_SERIAL_INDEX_KEY: Final = "romm:ps1_serial_index"
PS2_SERIAL_INDEX_KEY: Final = "romm:ps2_serial_index"
PSP_SERIAL_INDEX_KEY: Final = "romm:psp_serial_index"

LEADING_ARTICLE_PATTERN = re.compile(r"^(a|an|the)\b")
COMMA_ARTICLE_PATTERN = re.compile(r",\s(a|an|the)\b$")
NON_WORD_SPACE_PATTERN = re.compile(r"[^\w\s]")
MULTIPLE_SPACE_PATTERN = re.compile(r"\s+")


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


class MetadataHandler:
    def __init__(self):
        # Initialize cache data lazily when the handler is first instantiated
        conditionally_set_cache(MAME_XML_KEY, "mame_index.json")
        conditionally_set_cache(PS2_OPL_KEY, "ps2_opl_index.json")
        conditionally_set_cache(PS1_SERIAL_INDEX_KEY, "ps1_serial_index.json")
        conditionally_set_cache(PS2_SERIAL_INDEX_KEY, "ps2_serial_index.json")
        conditionally_set_cache(PSP_SERIAL_INDEX_KEY, "psp_serial_index.json")

    def normalize_cover_url(self, url: str) -> str:
        return url if not url else f"https:{url.replace('https:', '')}"

    def normalize_search_term(
        self, name: str, remove_articles: bool = True, remove_punctuation: bool = True
    ) -> str:
        return _normalize_search_term(name, remove_articles, remove_punctuation)

    async def _ps2_opl_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        index_entry = await async_cache.hget(PS2_OPL_KEY, serial_code)
        if index_entry:
            index_entry = json.loads(index_entry)
            search_term = index_entry["Name"]  # type: ignore

        return search_term

    async def _sony_serial_format(self, index_key: str, serial_code: str) -> str | None:
        index_entry = await async_cache.hget(index_key, serial_code)
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
            log.warning("Fetching the Switch titleID index file...")
            await update_switch_titledb_task.run(force=True)

            if not (await async_cache.exists(SWITCH_TITLEDB_INDEX_KEY)):
                log.error("Could not fetch the Switch titleID index file")
                return search_term, None

        index_entry = await async_cache.hget(SWITCH_TITLEDB_INDEX_KEY, title_id)
        if index_entry:
            index_entry = json.loads(index_entry)
            return index_entry["name"], index_entry

        return search_term, None

    async def _switch_productid_format(
        self, match: re.Match[str], search_term: str
    ) -> tuple[str, dict | None]:
        product_id = match.group(1)

        # Game updates have the same product ID as the main application, except with bitmask 0x800 set
        product_id = list(product_id)
        product_id[-3] = "0"
        product_id = "".join(product_id)

        if not (await async_cache.exists(SWITCH_PRODUCT_ID_KEY)):
            log.warning("Fetching the Switch productID index file...")
            await update_switch_titledb_task.run(force=True)

            if not (await async_cache.exists(SWITCH_PRODUCT_ID_KEY)):
                log.error("Could not fetch the Switch productID index file")
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

    def _mask_sensitive_values(self, values: dict[str, str]) -> dict[str, str]:
        """
        Mask sensitive values (headers or params), leaving only the first 3 and last 3 characters of the token.
        This is valid for a dictionary with any of the following keys:
            - "Authorization" (Bearer token)
            - "Client-ID"
            - "Client-Secret"
            - "client_id"
            - "client_secret"
            - "api_key"
            - "ssid"
            - "sspassword"
            - "devid"
            - "devpassword"
            - "y" (RA API key)
        """
        return {
            key: (
                f"Bearer {values[key].split(' ')[1][:2]}***{values[key].split(' ')[1][-2:]}"
                if key == "Authorization" and values[key].startswith("Bearer ")
                else (
                    f"{values[key][:2]}***{values[key][-2:]}"
                    if key
                    in {
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
                    # Leave other keys unchanged
                    else values[key]
                )
            )
            for key in values
        }
