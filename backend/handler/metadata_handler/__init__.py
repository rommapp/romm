import json
import xmltodict
import os
import re
import unicodedata
from typing import Final
from logger.logger import log
from handler.redis_handler import cache
from tasks.update_switch_titledb import (
    update_switch_titledb_task,
    SWITCH_TITLEDB_INDEX_KEY,
    SWITCH_PRODUCT_ID_KEY,
)

# These are loaded in cache in update_switch_titledb_task
SWITCH_TITLEDB_REGEX: Final = r"(70[0-9]{12})"
SWITCH_PRODUCT_ID_REGEX: Final = r"(0100[0-9A-F]{12})"

# No regex needed for MAME
MAME_XML_FILE: Final = os.path.join(os.path.dirname(__file__), "fixtures", "mame.xml")
mame_xml_data = xmltodict.parse(open(MAME_XML_FILE, "r").read())

# PS2 OPL
PS2_OPL_REGEX: Final = r"^([A-Z]{4}_\d{3}\.\d{2})\..*$"
PS2_OPL_INDEX_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "ps2_opl_index.json"
)
ps2_opl_index_data = json.loads(open(PS2_OPL_INDEX_FILE, "r").read())

# Sony serial codes for PS1, PS2, and PSP
SONY_SERIAL_REGEX: Final = r".*([a-zA-Z]{4}-\d{5}).*$"

PS1_SERIAL_INDEX_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "ps1_serial_index.json"
)
ps1_serial_index_data = json.loads(open(PS1_SERIAL_INDEX_FILE, "r").read())

PS2_SERIAL_INDEX_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "ps2_serial_index.json"
)
ps2_serial_index_data = json.loads(open(PS2_SERIAL_INDEX_FILE, "r").read())

PSP_SERIAL_INDEX_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "psp_serial_index.json"
)
psp_serial_index_data = json.loads(open(PSP_SERIAL_INDEX_FILE, "r").read())


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
        if not url:
            return url

        return f"https:{url.replace('https:', '')}"

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
        converted_name = "".join((re.findall(r"\w+", name)))

        # Convert to normal form
        normalized_name = unicodedata.normalize("NFD", converted_name)

        # Remove accents
        canonical_form = "".join(
            [c for c in normalized_name if not unicodedata.combining(c)]
        )

        return canonical_form

    async def _ps2_opl_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        index_entry = ps2_opl_index_data.get(serial_code, None)
        if index_entry:
            search_term = index_entry["Name"]  # type: ignore

        return search_term

    async def _sony_serial_format(
        self, index_data: dict, serial_code: str
    ) -> str | None:
        index_entry = index_data.get(serial_code.upper(), None)
        if index_entry:
            return index_entry["title"]

        return None

    async def _ps1_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return (
            await self._sony_serial_format(ps1_serial_index_data, serial_code)
            or search_term
        )

    async def _ps2_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return (
            await self._sony_serial_format(ps2_serial_index_data, serial_code)
            or search_term
        )

    async def _psp_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return (
            await self._sony_serial_format(psp_serial_index_data, serial_code)
            or search_term
        )

    async def _switch_titledb_format(
        self, match: re.Match[str], search_term: str
    ) -> tuple[str, dict | None]:
        title_id = match.group(1)

        if not cache.exists(SWITCH_TITLEDB_INDEX_KEY):
            log.warning("Fetching the Switch titleID index file...")
            await update_switch_titledb_task.run(force=True)

            if not cache.exists(SWITCH_TITLEDB_INDEX_KEY):
                log.error("Could not fetch the Switch titleID index file")
                return search_term, None

        switch_index = json.loads(cache.get(SWITCH_TITLEDB_INDEX_KEY))
        index_entry = switch_index.get(title_id, None)
        if index_entry:
            return index_entry["name"], index_entry  # type: ignore

        return search_term, None

    async def _switch_productid_format(
        self, match: re.Match[str], search_term: str
    ) -> tuple[str, dict | None]:
        product_id = match.group(1)

        # Game updates have the same product ID as the main application, except with bitmask 0x800 set
        product_id = list(product_id)
        product_id[-3] = "0"
        product_id = "".join(product_id)

        if not cache.exists(SWITCH_PRODUCT_ID_KEY):
            log.warning("Fetching the Switch productID index file...")
            await update_switch_titledb_task.run(force=True)

            if not cache.exists(SWITCH_PRODUCT_ID_KEY):
                log.error("Could not fetch the Switch productID index file")
                return search_term, None

        switch_index = json.loads(cache.get(SWITCH_PRODUCT_ID_KEY))
        index_entry = switch_index.get(product_id, None)
        if index_entry:
            return index_entry["name"], index_entry  # type: ignore

        return search_term, None

    async def _mame_format(self, search_term: str) -> str:
        from handler import fs_rom_handler

        index_entry = [
            game
            for game in mame_xml_data["menu"]["game"]
            if game["@name"] == search_term
        ]
        if index_entry:
            search_term = fs_rom_handler.get_file_name_with_no_tags(
                index_entry[0].get("description", search_term)
            )

        return search_term
