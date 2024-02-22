import json
import xmltodict
import os
import re
from typing import Final
from logger.logger import log
from tasks.update_mame_xml import update_mame_xml_task
from tasks.update_switch_titledb import update_switch_titledb_task


PS2_OPL_REGEX: Final = r"^([A-Z]{4}_\d{3}\.\d{2})\..*$"
PS2_OPL_INDEX_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "ps2_opl_index.json"
)

SWITCH_TITLEDB_REGEX: Final = r"(70[0-9]{12})"
SWITCH_TITLEDB_INDEX_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "switch_titledb.json"
)

SWITCH_PRODUCT_ID_REGEX: Final = r"(0100[0-9A-F]{12})"
SWITCH_PRODUCT_ID_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "switch_product_ids.json"
)

MAME_XML_FILE: Final = os.path.join(os.path.dirname(__file__), "fixtures", "mame.xml")

SONY_SERIAL_REGEX: Final = r".*([a-zA-Z]{4}-\d{5}).*$"
PS1_SERIAL_INDEX_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "ps1_serial_index.json"
)
PS2_SERIAL_INDEX_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "ps2_serial_index.json"
)
PSP_SERIAL_INDEX_FILE: Final = os.path.join(
    os.path.dirname(__file__), "fixtures", "psp_serial_index.json"
)

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

    async def _ps2_opl_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)

        with open(PS2_OPL_INDEX_FILE, "r") as index_json:
            opl_index = json.loads(index_json.read())
            index_entry = opl_index.get(serial_code, None)
            if index_entry:
                search_term = index_entry["Name"]  # type: ignore

        return search_term
    
    async def _sony_serial_format(self, index_file: str, serial_code: str) -> str | None:
        with open(index_file, "r") as index_json:
            opl_index = json.loads(index_json.read())
            index_entry = opl_index.get(serial_code.upper(), None)
            if index_entry:
                return index_entry["title"]

        return None
    
    async def _ps1_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return await self._sony_serial_format(PS1_SERIAL_INDEX_FILE, serial_code) or search_term
    
    async def _ps2_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return await self._sony_serial_format(PS2_SERIAL_INDEX_FILE, serial_code) or search_term
    
    async def _psp_serial_format(self, match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)
        return await self._sony_serial_format(PSP_SERIAL_INDEX_FILE, serial_code) or search_term

    async def _switch_titledb_format(
        self, match: re.Match[str], search_term: str
    ) -> str:
        titledb_index = {}
        title_id = match.group(1)

        try:
            with open(SWITCH_TITLEDB_INDEX_FILE, "r") as index_json:
                titledb_index = json.loads(index_json.read())
        except FileNotFoundError:
            log.warning("Fetching the Switch titleDB index file...")
            await update_switch_titledb_task.run(force=True)
            try:
                with open(SWITCH_TITLEDB_INDEX_FILE, "r") as index_json:
                    titledb_index = json.loads(index_json.read())
            except FileNotFoundError:
                log.error("Could not fetch the Switch titleDB index file")
        finally:
            index_entry = titledb_index.get(title_id, None)
            if index_entry:
                search_term = index_entry["name"]  # type: ignore

        return search_term

    async def _switch_productid_format(
        self, match: re.Match[str], search_term: str
    ) -> str:
        product_id_index = {}
        product_id = match.group(1)

        # Game updates have the same product ID as the main application, except with bitmask 0x800 set
        product_id = list(product_id)
        product_id[-3] = "0"
        product_id = "".join(product_id)

        try:
            with open(SWITCH_PRODUCT_ID_FILE, "r") as index_json:
                product_id_index = json.loads(index_json.read())
        except FileNotFoundError:
            log.warning("Fetching the Switch titleDB index file...")
            await update_switch_titledb_task.run(force=True)
            try:
                with open(SWITCH_PRODUCT_ID_FILE, "r") as index_json:
                    product_id_index = json.loads(index_json.read())
            except FileNotFoundError:
                log.error("Could not fetch the Switch titleDB index file")
        finally:
            index_entry = product_id_index.get(product_id, None)
            if index_entry:
                search_term = index_entry["name"]  # type: ignore
        return search_term

    async def _mame_format(self, search_term: str) -> str:
        from handler import fs_rom_handler

        mame_index = {"menu": {"game": []}}

        try:
            with open(MAME_XML_FILE, "r") as index_xml:
                mame_index = xmltodict.parse(index_xml.read())
        except FileNotFoundError:
            log.warning("Fetching the MAME XML file from HyperspinFE...")
            await update_mame_xml_task.run(force=True)
            try:
                with open(MAME_XML_FILE, "r") as index_xml:
                    mame_index = xmltodict.parse(index_xml.read())
            except FileNotFoundError:
                log.error("Could not fetch the MAME XML file from HyperspinFE")
        finally:
            index_entry = [
                game
                for game in mame_index["menu"]["game"]
                if game["@name"] == search_term
            ]
            if index_entry:
                search_term = fs_rom_handler.get_file_name_with_no_tags(
                    index_entry[0].get("description", search_term)
                )

        return search_term
