import functools
import json
import os
import re
import sys
import time
from typing import Final

import pydash
import requests
import xmltodict
from config import DEFAULT_URL_COVER_L, IGDB_CLIENT_ID, IGDB_CLIENT_SECRET
from logger.logger import log
from requests.exceptions import HTTPError, Timeout
from tasks.update_mame_xml import update_mame_xml_task
from tasks.update_switch_titledb import update_switch_titledb_task
from typing_extensions import TypedDict
from unidecode import unidecode as uc
from handler.redis_handler import cache

MAIN_GAME_CATEGORY: Final = 0
EXPANDED_GAME_CATEGORY: Final = 10
N_SCREENSHOTS: Final = 5
PS2_IGDB_ID: Final = 8
SWITCH_IGDB_ID: Final = 130
ARCADE_IGDB_IDS: Final = [52, 79, 80]

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


class IGDBPlatformType(TypedDict):
    igdb_id: int
    name: str


class IGDBRomType(TypedDict):
    igdb_id: int
    slug: str
    name: str
    summary: str
    url_cover: str
    url_screenshots: list[str]


class IGDBHandler:
    def __init__(self) -> None:
        self.platform_url = "https://api.igdb.com/v4/platforms/"
        self.games_url = "https://api.igdb.com/v4/games/"
        self.covers_url = "https://api.igdb.com/v4/covers/"
        self.screenshots_url = "https://api.igdb.com/v4/screenshots/"
        self.twitch_auth = TwitchAuth()
        self.headers = {
            "Client-ID": IGDB_CLIENT_ID,
            "Authorization": f"Bearer {self.twitch_auth.get_oauth_token()}",
            "Accept": "application/json",
        }

    @staticmethod
    def check_twitch_token(func):
        @functools.wraps(func)
        def wrapper(*args):
            args[0].headers[
                "Authorization"
            ] = f"Bearer {args[0].twitch_auth.get_oauth_token()}"
            return func(*args)

        return wrapper
    
    @staticmethod
    def normalize_search_term(search_term: str) -> str:
        return (
            search_term.replace("\u2122", "")  # Remove trademark symbol
            .replace("\u00ae", "")  # Remove registered symbol
            .replace("\u00a9", "")  # Remove copywrite symbol
            .replace("\u2120", "")  # Remove service mark symbol
            .strip()  # Remove leading and trailing spaces
        )

    def _request(self, url: str, data: str, timeout: int = 120) -> list:
        try:
            res = requests.post(url, data, headers=self.headers, timeout=timeout)
            res.raise_for_status()
            return res.json()
        except HTTPError as err:
            # Retry once if the auth token is invalid
            if err.response.status_code != 401:
                log.error(err)
                return []  # All requests to the IGDB API return a list

            # Attempt to force a token refresh if the token is invalid
            log.warning("Twitch token invalid: fetching a new one...")
            token = self.twitch_auth._update_twitch_token()
            self.headers["Authorization"] = f"Bearer {token}"
        except Timeout:
            # Retry once the request if it times out
            pass

        try:
            res = requests.post(url, data, headers=self.headers, timeout=timeout)
            res.raise_for_status()
        except (HTTPError, Timeout) as err:
            # Log the error and return an empty list if the request fails again
            log.error(err)
            return []

        return res.json()

    def _search_rom(
        self, search_term: str, platform_idgb_id: int, category: int = 0
    ) -> dict:
        category_filter: str = f"& category={category}" if category else ""
        roms = self._request(
            self.games_url,
            data=f"""
                search "{search_term}";
                fields id, slug, name, summary, screenshots;
                where platforms=[{platform_idgb_id}] {category_filter};
            """,
        )

        exact_matches = [
            rom
            for rom in roms
            if rom["name"].lower() == search_term.lower()
            or rom["slug"].lower() == search_term.lower()
        ]

        return pydash.get(exact_matches or roms, "[0]", {})

    @staticmethod
    def _normalize_cover_url(url: str) -> str:
        return f"https:{url.replace('https:', '')}"

    def _search_cover(self, rom_id: int) -> str:
        covers = self._request(
            self.covers_url,
            data=f"fields url; where game={rom_id};",
        )

        cover = pydash.get(covers, "[0]", None)
        return (
            DEFAULT_URL_COVER_L
            if not cover
            else self._normalize_cover_url(cover["url"])
        )

    def _search_screenshots(self, rom_id: int) -> list:
        screenshots = self._request(
            self.screenshots_url,
            data=f"fields url; where game={rom_id}; limit {N_SCREENSHOTS};",
        )

        return [
            self._normalize_cover_url(r["url"]).replace("t_thumb", "t_original")
            for r in screenshots
            if "url" in r.keys()
        ]

    @staticmethod
    async def _ps2_opl_format(match: re.Match[str], search_term: str) -> str:
        serial_code = match.group(1)

        with open(PS2_OPL_INDEX_FILE, "r") as index_json:
            opl_index = json.loads(index_json.read())
            index_entry = opl_index.get(serial_code, None)
            if index_entry:
                search_term = index_entry["Name"]  # type: ignore

        return search_term

    @staticmethod
    async def _switch_titledb_format(match: re.Match[str], search_term: str) -> str:
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

    @staticmethod
    async def _switch_productid_format(match: re.Match[str], search_term: str) -> str:
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
                # Run through get_search_term to remove tags
                # TODO: refactor
                from handler.fs_handler.fs_handler import FSHandler
                get_search_term = FSHandler.get_file_name_with_no_tags
                search_term = get_search_term(
                    index_entry[0].get("description", search_term)
                )

        return search_term

    @check_twitch_token
    def get_platform(self, slug: str) -> IGDBPlatformType:
        platforms = self._request(
            self.platform_url,
            data=f'fields id, name; where slug="{slug.lower()}";',
        )

        platform = pydash.get(platforms, "[0]", None)
        if not platform:
            return IGDBPlatformType(igdb_id=None, name=slug.replace("-", " ").title())

        return IGDBPlatformType(
            igdb_id=platform["id"],
            name=platform["name"],
        )

    @check_twitch_token
    async def get_rom(self, file_name: str, platform_idgb_id: int) -> IGDBRomType:
        # TODO: refactor
        from handler.fs_handler.fs_handler import FSHandler
        get_search_term = FSHandler.get_file_name_with_no_tags
        search_term = get_search_term(file_name)

        # Support for PS2 OPL filename format
        match = re.match(PS2_OPL_REGEX, file_name)
        if platform_idgb_id == PS2_IGDB_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)

        # Support for switch titleID filename format
        match = re.search(SWITCH_TITLEDB_REGEX, file_name)
        if platform_idgb_id == SWITCH_IGDB_ID and match:
            search_term = await self._switch_titledb_format(match, search_term)

        # Support for switch productID filename format
        match = re.search(SWITCH_PRODUCT_ID_REGEX, file_name)
        if platform_idgb_id == SWITCH_IGDB_ID and match:
            search_term = await self._switch_productid_format(match, search_term)

        # Support for MAME arcade filename format
        if platform_idgb_id in ARCADE_IGDB_IDS:
            search_term = await self._mame_format(search_term)

        search_term = self.normalize_search_term(search_term)

        res = (
            self._search_rom(uc(search_term), platform_idgb_id, MAIN_GAME_CATEGORY)
            or self._search_rom(
                uc(search_term), platform_idgb_id, EXPANDED_GAME_CATEGORY
            )
            or self._search_rom(uc(search_term), platform_idgb_id)
        )

        igdb_id = res.get("id", None)
        rom = IGDBRomType(
            igdb_id=igdb_id,
            slug=res.get("slug", ""),
            name=res.get("name", search_term),
            summary=res.get("summary", ""),
            url_cover=DEFAULT_URL_COVER_L,
            url_screenshots=[],
        )

        if igdb_id:
            rom["url_cover"] = self._search_cover(igdb_id)
            rom["url_screenshots"] = self._search_screenshots(igdb_id)

        return rom

    @check_twitch_token
    def get_rom_by_id(self, igdb_id: int) -> IGDBRomType:
        roms = self._request(
            self.games_url,
            f"fields slug, name, summary; where id={igdb_id};",
        )
        rom = pydash.get(roms, "[0]", {})

        return {
            "igdb_id": igdb_id,
            "slug": rom.get("slug", ""),
            "name": rom.get("name", ""),
            "summary": rom.get("summary", ""),
            "url_cover": self._search_cover(igdb_id),
            "url_screenshots": self._search_screenshots(igdb_id),
        }

    @check_twitch_token
    def get_matched_roms_by_id(self, igdb_id: int) -> list[IGDBRomType]:
        matched_rom = self.get_rom_by_id(igdb_id)
        matched_rom.update(
            url_cover=matched_rom["url_cover"].replace("t_thumb", "t_cover_big"),
        )
        return [matched_rom]

    @check_twitch_token
    def get_matched_roms_by_name(
        self, search_term: str, platform_idgb_id: int
    ) -> list[IGDBRomType]:
        if not platform_idgb_id:
            return []

        matched_roms = self._request(
            self.games_url,
            data=f"""
                search "{uc(search_term)}";
                fields id, slug, name, summary;
                where platforms=[{platform_idgb_id}];
            """,
        )

        return [
            IGDBRomType(
                igdb_id=rom["id"],
                slug=rom["slug"],
                name=rom["name"],
                summary=rom.get("summary", ""),
                url_cover=self._search_cover(rom["id"]).replace(
                    "t_thumb", "t_cover_big"
                ),
                url_screenshots=self._search_screenshots(rom["id"]),
            )
            for rom in matched_roms
        ]


class TwitchAuth:
    def _update_twitch_token(self) -> str:
        res = requests.post(
            url="https://id.twitch.tv/oauth2/token",
            params={
                "client_id": IGDB_CLIENT_ID,
                "client_secret": IGDB_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
            timeout=30,
        ).json()

        token = res.get("access_token", "")
        expires_in = res.get("expires_in", 0)
        if not token or expires_in == 0:
            log.error(
                "Could not get twitch auth token: check client_id and client_secret"
            )
            sys.exit(2)

        # Set token in redis to expire in <expires_in> seconds
        cache.set("romm:twitch_token", token, ex=expires_in - 10)  # type: ignore[attr-defined]
        cache.set("romm:twitch_token_expires_at", time.time() + expires_in - 10)  # type: ignore[attr-defined]

        log.info("Twitch token fetched!")

        return token

    def get_oauth_token(self) -> str:
        # Use a fake token when running tests
        if "pytest" in sys.modules:
            return "test_token"

        # Fetch the token cache
        token = cache.get("romm:twitch_token")  # type: ignore[attr-defined]
        token_expires_at = cache.get("romm:twitch_token_expires_at")  # type: ignore[attr-defined]

        if not token or time.time() > float(token_expires_at or 0):
            log.warning("Twitch token invalid: fetching a new one...")
            return self._update_twitch_token()

        return token
