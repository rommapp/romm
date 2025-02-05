import asyncio
import base64
import http
import re
from typing import Final, NotRequired, TypedDict
from urllib.parse import quote

import httpx
import pydash
import yarl
from config import SCREENSCRAPER_PASSWORD, SCREENSCRAPER_USER
from fastapi import HTTPException, status
from logger.logger import log
from unidecode import unidecode as uc
from utils.context import ctx_httpx_client

from .base_hander import (
    PS2_OPL_REGEX,
    SONY_SERIAL_REGEX,
    SWITCH_PRODUCT_ID_REGEX,
    SWITCH_TITLEDB_REGEX,
    MetadataHandler,
)

# Used to display the Screenscraper API status in the frontend
SS_API_ENABLED: Final = bool(SCREENSCRAPER_USER) and bool(SCREENSCRAPER_PASSWORD)
SS_DEV_ID: Final = base64.b64decode("enVyZGkxNQ==").decode()
SS_DEV_PASSWORD: Final = base64.b64decode("eFRKd29PRmpPUUc=").decode()

PS1_SS_ID: Final = 57
PS2_SS_ID: Final = 58
PSP_SS_ID: Final = 61
SWITCH_SS_ID: Final = 225
ARCADE_SS_IDS: Final = [
    6,
    7,
    8,
    47,
    49,
    52,
    53,
    54,
    55,
    56,
    68,
    69,
    75,
    112,
    142,
    147,
    148,
    149,
    150,
    151,
    152,
    153,
    154,
    155,
    156,
    157,
    158,
    159,
    160,
    161,
    162,
    163,
    164,
    165,
    166,
    167,
    168,
    169,
    170,
    173,
    174,
    175,
    176,
    177,
    178,
    179,
    180,
    181,
    182,
    183,
    184,
    185,
    186,
    187,
    188,
    189,
    190,
    191,
    192,
    193,
    194,
    195,
    196,
    209,
    227,
    130,
    158,
    269,
]


class SSGamesPlatform(TypedDict):
    slug: str
    ss_id: int | None
    name: NotRequired[str]


class SSMetadataPlatform(TypedDict):
    ss_id: int
    name: str


class SSMetadata(TypedDict):
    ss_score: str
    genres: list[str]
    alternate_titles: list[str]
    platforms: list[SSMetadataPlatform]


class SSGamesRom(TypedDict):
    ss_id: int | None
    slug: NotRequired[str]
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    ss_metadata: NotRequired[SSMetadata]


def extract_metadata_from_ss_rom(rom: dict) -> SSMetadata:
    return SSMetadata(
        {
            "ss_score": "",
            "genres": [],
            "alternate_titles": [],
            "platforms": [],
        }
    )


class SSBaseHandler(MetadataHandler):
    def __init__(self) -> None:
        self.BASE_URL = "https://api.screenscraper.fr/api2"
        self.search_endpoint = f"{self.BASE_URL}/jeuRecherche.php"
        self.platform_endpoint = f"{self.BASE_URL}/systemesListe.php"
        self.games_endpoint = f"{self.BASE_URL}/jeuInfos.php"
        self.LOGIN_ERROR_CHECK: Final = "Erreur de login"
        self.NO_GAME_ERROR: Final = "Erreur : Jeu non trouvée !"

    @staticmethod
    def _extract_value_by_region(data_list, key, target_value):
        """Extract the first matching value by region."""
        for item in data_list:
            if item.get("region") == target_value:
                return item.get(key, "")
        return ""

    @staticmethod
    def _extract_value_by_language(data_list, key, target_language):
        """Extract the first matching value by language."""
        for item in data_list:
            if item.get("langue") == target_language:
                return item.get(key, "")
        return ""

    @staticmethod
    def _extract_box2d_cover_url(data_list):
        """Extract the first matching cover URL."""
        for item in data_list:
            if (
                item.get("region") == "us"
                and item.get("type") == "box-2D"
                and item.get("parent") == "jeu"
            ):
                return item.get("url", "")
        return ""

    async def _request(self, url: str, timeout: int = 120) -> dict:
        httpx_client = ctx_httpx_client.get()
        authorized_url = yarl.URL(url).update_query(
            ssid=SCREENSCRAPER_USER,
            sspassword=SCREENSCRAPER_PASSWORD,
            devid=SS_DEV_ID,
            devpassword=SS_DEV_PASSWORD,
            softname="romm",
            output="json",
        )
        masked_url = authorized_url.with_query(
            self._mask_sensitive_values(dict(authorized_url.query))
        )

        log.debug(
            "API request: URL=%s, Timeout=%s",
            masked_url,
            timeout,
        )

        try:
            res = await httpx_client.get(str(authorized_url), timeout=timeout)
            res.raise_for_status()
            if self.LOGIN_ERROR_CHECK in res.text:
                log.error("Invalid screenscraper credentials")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid screenscraper credentials",
                )
            elif self.NO_GAME_ERROR in res.text:
                return {}
            return res.json()
        except httpx.NetworkError as exc:
            log.critical(
                "Connection error: can't connect to Screenscrapper", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to Screenscrapper, check your internet connection",
            ) from exc
        except httpx.HTTPStatusError as err:
            if err.response.status_code == http.HTTPStatus.UNAUTHORIZED:
                # Sometimes Screenscrapper returns 401 even with a valid API key
                log.error(err)
                return {}
            elif err.response.status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
                # Retry after 2 seconds if rate limit hit
                await asyncio.sleep(2)
            else:
                # Log the error and return an empty dict if the request fails with a different code
                log.error(err)
                return {}
        except httpx.TimeoutException:
            log.debug(
                "Request to URL=%s timed out. Retrying with URL=%s", masked_url, url
            )
            # Retry the request once if it times out
        try:
            log.debug(
                "API request: URL=%s, Timeout=%s",
                url,
                timeout,
            )
            res = await httpx_client.get(url, timeout=timeout)
            res.raise_for_status()
            if self.LOGIN_ERROR_CHECK in res.text:
                log.error("Invalid screenscraper credentials")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid screenscraper credentials",
                )
            elif self.NO_GAME_ERROR in res.text:
                return {}
        except (httpx.HTTPStatusError, httpx.TimeoutException) as err:
            # Log the error and return an empty dict if the request fails with a different code
            log.error(err)
            return {}

        return res.json()

    async def _search_rom(self, search_term: str, platform_ss_id: int) -> dict | None:
        if not platform_ss_id:
            return None

        search_term = uc(search_term)
        url = yarl.URL(self.search_endpoint).with_query(
            systemeid=[platform_ss_id],
            recherche=quote(search_term, safe="/ "),
        )
        found_roms = (await self._request(str(url))).get("response", {}).get("jeux", [])
        # If no roms are return, "jeux" is list with an empty dict that can lead to issues. It needs to be checked.
        roms = [] if len(found_roms) == 1 and not found_roms[0] else found_roms
        return pydash.get(roms, "[0]", None)

    def get_platform(self, slug: str) -> SSGamesPlatform:
        platform = SLUG_TO_SS_ID.get(slug, None)

        if not platform:
            return SSGamesPlatform(ss_id=None, slug=slug)

        return SSGamesPlatform(
            ss_id=platform["id"],
            slug=slug,
            name=platform["name"],
        )

    async def get_rom(self, file_name: str, platform_ss_id: int) -> SSGamesRom:
        from handler.filesystem import fs_rom_handler

        if not SS_API_ENABLED:
            return SSGamesRom(ss_id=None)

        if not platform_ss_id:
            return SSGamesRom(ss_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(file_name)
        fallback_rom = SSGamesRom(ss_id=None)

        # Support for PS2 OPL filename format
        match = PS2_OPL_REGEX.match(file_name)
        if platform_ss_id == PS2_SS_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom = SSGamesRom(ss_id=None, name=search_term)

        # Support for sony serial filename format (PS, PS3, PS3)
        match = SONY_SERIAL_REGEX.search(file_name, re.IGNORECASE)
        if platform_ss_id == PS1_SS_ID and match:
            search_term = await self._ps1_serial_format(match, search_term)
            fallback_rom = SSGamesRom(ss_id=None, name=search_term)

        if platform_ss_id == PS2_SS_ID and match:
            search_term = await self._ps2_serial_format(match, search_term)
            fallback_rom = SSGamesRom(ss_id=None, name=search_term)

        if platform_ss_id == PSP_SS_ID and match:
            search_term = await self._psp_serial_format(match, search_term)
            fallback_rom = SSGamesRom(ss_id=None, name=search_term)

        # Support for switch titleID filename format
        match = SWITCH_TITLEDB_REGEX.search(file_name)
        if platform_ss_id == SWITCH_SS_ID and match:
            search_term, index_entry = await self._switch_titledb_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = SSGamesRom(
                    ss_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for switch productID filename format
        match = SWITCH_PRODUCT_ID_REGEX.search(file_name)
        if platform_ss_id == SWITCH_SS_ID and match:
            search_term, index_entry = await self._switch_productid_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = SSGamesRom(
                    ss_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for MAME arcade filename format
        if platform_ss_id in ARCADE_SS_IDS:
            search_term = await self._mame_format(search_term)
            fallback_rom = SSGamesRom(ss_id=None, name=search_term)

        search_term = self.normalize_search_term(search_term)
        res = await self._search_rom(search_term, platform_ss_id)

        # Some MAME games have two titles split by a slash
        if not res and "/" in search_term:
            for term in search_term.split("/"):
                res = await self._search_rom(term.strip(), platform_ss_id)
                if res:
                    break

        if not res:
            return fallback_rom

        rom = {
            "ss_id": res.get("id"),
            "name": self._extract_value_by_region(res.get("noms", []), "text", "ss"),
            "slug": self._extract_value_by_region(res.get("noms", []), "text", "ss"),
            "summary": self._extract_value_by_language(
                res.get("synopsis", []), "text", "en"
            ),
            "url_cover": self._extract_box2d_cover_url(res.get("medias", [])),
            "url_screenshots": [],
            "ss_metadata": extract_metadata_from_ss_rom(res),
        }

        return SSGamesRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_rom_by_id(self, ss_id: int) -> SSGamesRom:
        if not SS_API_ENABLED:
            return SSGamesRom(ss_id=None)

        url = yarl.URL(self.games_endpoint).with_query(gameid=ss_id)
        res = (await self._request(str(url))).get("response", {}).get("jeu", [])

        if not res:
            return SSGamesRom(ss_id=None)

        rom = {
            "ss_id": res.get("id"),
            "name": self._extract_value_by_region(res.get("noms", []), "text", "ss"),
            "slug": self._extract_value_by_region(res.get("noms", []), "text", "ss"),
            "summary": self._extract_value_by_language(
                res.get("synopsis", []), "text", "en"
            ),
            "url_cover": self._extract_box2d_cover_url(res.get("medias", [])),
            "url_screenshots": [],
            "ss_metadata": extract_metadata_from_ss_rom(res),
        }

        return SSGamesRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_matched_rom_by_id(self, ss_id: int) -> SSGamesRom | None:
        if not SS_API_ENABLED:
            return None

        rom = await self.get_rom_by_id(ss_id)
        return rom if rom.get("ss_id", "") else None

    async def get_matched_roms_by_name(
        self, search_term: str, platform_ss_id: int
    ) -> list[SSGamesRom]:
        # TODO: migrate to put all SS platform IDs in the database
        if not SS_API_ENABLED:
            return []

        if not platform_ss_id:
            return []

        search_term = uc(search_term)
        url = yarl.URL(self.search_endpoint).with_query(
            systemeid=[platform_ss_id],
            recherche=quote(search_term, safe="/ "),
        )
        roms = (await self._request(str(url))).get("response", {}).get("jeux", [])
        # If no roms are return, "jeux" is list with an empty dict that can lead to issues. It needs to be checked.
        matched_roms = [] if len(roms) == 1 and not roms[0] else roms

        return [
            SSGamesRom(  # type: ignore[misc]
                {
                    k: v
                    for k, v in {
                        "ss_id": rom.get("id"),
                        "name": self._extract_value_by_region(
                            rom.get("noms", []), "text", "ss"
                        ),
                        "slug": self._extract_value_by_region(
                            rom.get("noms", []), "text", "ss"
                        ),
                        "summary": self._extract_value_by_language(
                            rom.get("synopsis", []), "text", "en"
                        ),
                        "url_cover": self._extract_box2d_cover_url(
                            rom.get("medias", [])
                        ),
                        "url_screenshots": [],
                        "ss_metadata": extract_metadata_from_ss_rom(rom),
                    }.items()
                    if v
                    and self._extract_value_by_region(rom.get("noms", []), "text", "ss")
                    and rom.get("id", None)
                }
            )
            for rom in matched_roms
        ]


class SlugToSSId(TypedDict):
    id: int
    name: str


SLUG_TO_SS_ID: dict[str, SlugToSSId] = {
    "3do": {"id": 29, "name": "3DO"},
    "acorn-electron": {"id": 85, "name": "Acorn Electron"},
    "dc": {"id": 23, "name": "Dreamcast"},
    "gb": {"id": 9, "name": "Game Boy"},
    "gba": {"id": 12, "name": "Game Boy Advance"},
    "gbc": {"id": 10, "name": "Game Boy Color"},
    "switch": {"id": 225, "name": "Nintendo Switch"},
    "win": {"id": 138, "name": "Microsoft Windows (PC)"},
}

# Reverse lookup
SS_ID_TO_SLUG = {v["id"]: k for k, v in SLUG_TO_SS_ID.items()}
