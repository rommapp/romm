import json
import os
import re
import unicodedata
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
    fixtures_path = os.path.join(parent_dir, "fixtures")
    if not sync_cache.exists(index_key):
        index_data = json.loads(open(os.path.join(fixtures_path, filename)).read())
        with sync_cache.pipeline() as pipe:
            for data_batch in batched(index_data.items(), 2000):
                data_map = {k: json.dumps(v) for k, v in dict(data_batch).items()}
                pipe.hset(index_key, mapping=data_map)
            pipe.execute()


# These are loaded in cache in update_switch_titledb_task
SWITCH_TITLEDB_REGEX: Final = re.compile(r"(70[0-9]{12})")
SWITCH_PRODUCT_ID_REGEX: Final = re.compile(r"(0100[0-9A-F]{12})")


# No regex needed for MAME
MAME_XML_KEY: Final = "romm:mame_xml"
conditionally_set_cache(MAME_XML_KEY, "mame_index.json")

# PS2 OPL
PS2_OPL_REGEX: Final = re.compile(r"^([A-Z]{4}_\d{3}\.\d{2})\..*$")
PS2_OPL_KEY: Final = "romm:ps2_opl_index"
conditionally_set_cache(PS2_OPL_KEY, "ps2_opl_index.json")

# Sony serial codes for PS1, PS2, and PSP
SONY_SERIAL_REGEX: Final = re.compile(r".*([a-zA-Z]{4}-\d{5}).*$")

PS1_SERIAL_INDEX_KEY: Final = "romm:ps1_serial_index"
conditionally_set_cache(PS1_SERIAL_INDEX_KEY, "ps1_serial_index.json")

PS2_SERIAL_INDEX_KEY: Final = "romm:ps2_serial_index"
conditionally_set_cache(PS2_SERIAL_INDEX_KEY, "ps2_serial_index.json")

PSP_SERIAL_INDEX_KEY: Final = "romm:psp_serial_index"
conditionally_set_cache(PSP_SERIAL_INDEX_KEY, "psp_serial_index.json")


class MetadataHandler:
    @staticmethod
    def normalize_search_term(search_term: str) -> str:
        return (
            search_term.replace("\u2122", "")  # Remove trademark symbol
            .replace("\u00ae", "")  # Remove registered symbol
            .replace("\u00a9", "")  # Remove copywrite symbol
            .replace("\u2120", "")  # Remove service mark symbol
            .strip()  # Remove leading and trailing spaces
        )

    @staticmethod
    def _normalize_cover_url(url: str) -> str:
        return url if not url else f"https:{url.replace('https:', '')}"

    # This is expensive, so it should be used sparingly
    @staticmethod
    def _normalize_exact_match(name: str) -> str:
        name = (
            name.lower()  # Convert to lower case,
            .replace("_", " ")  # Replace underscores with spaces
            .replace("'", "")  # Remove single quotes
            .replace('"', "")  # Remove double quotes
            .strip()  # Remove leading and trailing spaces
        )

        # Remove leading and trailing articles
        name = re.sub(r"^(a|an|the)\b", "", name)
        name = re.sub(r",\b(a|an|the)\b", "", name)

        # Remove special characters and punctuation
        converted_name = "".join(re.findall(r"\w+", name))

        # Convert to normal form
        normalized_name = unicodedata.normalize("NFD", converted_name)

        # Remove accents
        canonical_form = "".join(
            [c for c in normalized_name if not unicodedata.combining(c)]
        )

        return canonical_form

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
