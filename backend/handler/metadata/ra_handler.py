import asyncio
import http
import re
from typing import Final, NotRequired, TypedDict
from urllib.parse import quote

import httpx
import pydash
import yarl
from config import RETROACHIEVEMENTS_API_KEY, RETROACHIEVEMENTS_USERNAME
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

# Used to display the RetroAchievements API status in the frontend
RA_API_ENABLED: Final = bool(RETROACHIEVEMENTS_API_KEY) and bool(
    RETROACHIEVEMENTS_USERNAME
)

PS1_MOBY_ID: Final = 6
PS2_MOBY_ID: Final = 7
PSP_MOBY_ID: Final = 46
SWITCH_MOBY_ID: Final = 203
ARCADE_MOBY_IDS: Final = [143, 36]


class RAGamesPlatform(TypedDict):
    slug: str
    moby_id: int | None
    name: NotRequired[str]


class RAMetadataPlatform(TypedDict):
    ra_id: int
    name: str


class RAMetadata(TypedDict):
    moby_score: str
    genres: list[str]
    alternate_titles: list[str]
    platforms: list[RAMetadataPlatform]


class RAGameRom(TypedDict):
    moby_id: int | None
    slug: NotRequired[str]
    name: NotRequired[str]
    summary: NotRequired[str]
    url_cover: NotRequired[str]
    url_screenshots: NotRequired[list[str]]
    moby_metadata: NotRequired[RAMetadata]


def extract_metadata_from_moby_rom(rom: dict) -> RAMetadata:
    return RAMetadata(
        {
            "moby_score": str(rom.get("moby_score", "")),
            "genres": rom.get("genres.genre_name", []),
            "alternate_titles": rom.get("alternate_titles.title", []),
            "platforms": [
                {
                    "moby_id": p["platform_id"],
                    "name": p["platform_name"],
                }
                for p in rom.get("platforms", [])
            ],
        }
    )


class RetroAchievementsHandler(MetadataHandler):
    def __init__(self) -> None:
        self.platform_url = (
            "https://retroachievements.org/API/API_GetGameList.php?&h=1&f=1"
        )
        self.games_url = "https://api.mobygames.com/v1/games"

    async def _request(self, url: str, timeout: int = 120) -> dict:
        httpx_client = ctx_httpx_client.get()
        authorized_url = (
            yarl.URL(url)
            .update_query(z=RETROACHIEVEMENTS_USERNAME)
            .update_query(y=RETROACHIEVEMENTS_API_KEY)
        )
        try:
            res = await httpx_client.get(str(authorized_url), timeout=timeout)
            res.raise_for_status()
            return res.json()
        except httpx.NetworkError as exc:
            log.critical(
                "Connection error: can't connect to RetroAchievements", exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Can't connect to RetroAchievements, check your internet connection",
            ) from exc
        except httpx.HTTPStatusError as err:
            if err.response.status_code == http.HTTPStatus.TOO_MANY_REQUESTS:
                # Retry after 2 seconds if rate limit hit
                await asyncio.sleep(2)
            else:
                # Log the error and return an empty dict if the request fails with a different code
                log.error(err)
                return {}
        except httpx.TimeoutException:
            # Retry the request once if it times out
            pass

        try:
            res = await httpx_client.get(url, timeout=timeout)
            res.raise_for_status()
        except (httpx.HTTPStatusError, httpx.TimeoutException) as err:
            if (
                isinstance(err, httpx.HTTPStatusError)
                and err.response.status_code == http.HTTPStatus.UNAUTHORIZED
            ):
                # Sometimes Mobygames returns 401 even with a valid API key
                return {}

            # Log the error and return an empty dict if the request fails with a different code
            log.error(err)
            return {}

        return res.json()

    async def _search_rom(self, search_term: str, platform_moby_id: int) -> dict | None:
        if not platform_moby_id:
            return None

        search_term = uc(search_term)
        url = yarl.URL(self.games_url).with_query(
            platform=[platform_moby_id],
            title=quote(search_term, safe="/ "),
        )
        roms = (await self._request(str(url))).get("games", [])

        exact_matches = [
            rom
            for rom in roms
            if (
                rom["title"].lower() == search_term.lower()
                or (
                    self._normalize_exact_match(rom["title"])
                    == self._normalize_exact_match(search_term)
                )
            )
        ]

        return pydash.get(exact_matches or roms, "[0]", None)

    def get_platform(self, slug: str) -> RAGamesPlatform:
        platform = SLUG_TO_RA_ID.get(slug.lower(), None)

        print(platform)

        if not platform:
            return RAGamesPlatform(ra_id=None, slug=slug)

        return RAGamesPlatform(
            ra_id=platform["id"],
            slug=slug,
            name=platform["name"],
        )

    async def get_rom(self, file_name: str, platform_moby_id: int) -> RAGameRom:
        from handler.filesystem import fs_rom_handler

        if not RA_API_ENABLED:
            return RAGameRom(moby_id=None)

        if not platform_moby_id:
            return RAGameRom(moby_id=None)

        search_term = fs_rom_handler.get_file_name_with_no_tags(file_name)
        fallback_rom = RAGameRom(moby_id=None)

        # Support for PS2 OPL filename format
        match = PS2_OPL_REGEX.match(file_name)
        if platform_moby_id == PS2_MOBY_ID and match:
            search_term = await self._ps2_opl_format(match, search_term)
            fallback_rom = RAGameRom(moby_id=None, name=search_term)

        # Support for sony serial filename format (PS, PS3, PS3)
        match = SONY_SERIAL_REGEX.search(file_name, re.IGNORECASE)
        if platform_moby_id == PS1_MOBY_ID and match:
            search_term = await self._ps1_serial_format(match, search_term)
            fallback_rom = RAGameRom(moby_id=None, name=search_term)

        if platform_moby_id == PS2_MOBY_ID and match:
            search_term = await self._ps2_serial_format(match, search_term)
            fallback_rom = RAGameRom(moby_id=None, name=search_term)

        if platform_moby_id == PSP_MOBY_ID and match:
            search_term = await self._psp_serial_format(match, search_term)
            fallback_rom = RAGameRom(moby_id=None, name=search_term)

        # Support for switch titleID filename format
        match = SWITCH_TITLEDB_REGEX.search(file_name)
        if platform_moby_id == SWITCH_MOBY_ID and match:
            search_term, index_entry = await self._switch_titledb_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = RAGameRom(
                    moby_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for switch productID filename format
        match = SWITCH_PRODUCT_ID_REGEX.search(file_name)
        if platform_moby_id == SWITCH_MOBY_ID and match:
            search_term, index_entry = await self._switch_productid_format(
                match, search_term
            )
            if index_entry:
                fallback_rom = RAGameRom(
                    moby_id=None,
                    name=index_entry["name"],
                    summary=index_entry.get("description", ""),
                    url_cover=index_entry.get("iconUrl", ""),
                    url_screenshots=index_entry.get("screenshots", None) or [],
                )

        # Support for MAME arcade filename format
        if platform_moby_id in ARCADE_MOBY_IDS:
            search_term = await self._mame_format(search_term)
            fallback_rom = RAGameRom(moby_id=None, name=search_term)

        search_term = self.normalize_search_term(search_term)
        res = await self._search_rom(search_term, platform_moby_id)

        # Split the search term since mobygames search doesn't support special caracters
        if not res and ":" in search_term:
            for term in search_term.split(":")[::-1]:
                res = await self._search_rom(term, platform_moby_id)
                if res:
                    break

        # Some MAME games have two titles split by a slash
        if not res and "/" in search_term:
            for term in search_term.split("/"):
                res = await self._search_rom(term.strip(), platform_moby_id)
                if res:
                    break

        if not res:
            return fallback_rom

        rom = {
            "moby_id": res["game_id"],
            "name": res["title"],
            "slug": res["moby_url"].split("/")[-1],
            "summary": res.get("description", ""),
            "url_cover": pydash.get(res, "sample_cover.image", ""),
            "url_screenshots": [s["image"] for s in res.get("sample_screenshots", [])],
            "moby_metadata": extract_metadata_from_moby_rom(res),
        }

        return RAGameRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_rom_by_id(self, moby_id: int) -> RAGameRom:
        if not RA_API_ENABLED:
            return RAGameRom(moby_id=None)

        url = yarl.URL(self.games_url).with_query(id=moby_id)
        roms = (await self._request(str(url))).get("games", [])
        res = pydash.get(roms, "[0]", None)

        if not res:
            return RAGameRom(moby_id=None)

        rom = {
            "moby_id": res["game_id"],
            "name": res["title"],
            "slug": res["moby_url"].split("/")[-1],
            "summary": res.get("description", None),
            "url_cover": pydash.get(res, "sample_cover.image", None),
            "url_screenshots": [s["image"] for s in res.get("sample_screenshots", [])],
            "moby_metadata": extract_metadata_from_moby_rom(res),
        }

        return RAGameRom({k: v for k, v in rom.items() if v})  # type: ignore[misc]

    async def get_matched_roms_by_id(self, moby_id: int) -> list[RAGameRom]:
        if not RA_API_ENABLED:
            return []

        rom = await self.get_rom_by_id(moby_id)
        return [rom] if rom["moby_id"] else []

    async def get_matched_roms_by_name(
        self, search_term: str, platform_moby_id: int
    ) -> list[RAGameRom]:
        if not RA_API_ENABLED:
            return []

        if not platform_moby_id:
            return []

        search_term = uc(search_term)
        url = yarl.URL(self.games_url).with_query(
            platform=[platform_moby_id], title=quote(search_term, safe="/ ")
        )
        matched_roms = (await self._request(str(url))).get("games", [])

        return [
            RAGameRom(  # type: ignore[misc]
                {
                    k: v
                    for k, v in {
                        "moby_id": rom["game_id"],
                        "name": rom["title"],
                        "slug": rom["moby_url"].split("/")[-1],
                        "summary": rom.get("description", ""),
                        "url_cover": pydash.get(rom, "sample_cover.image", ""),
                        "url_screenshots": [
                            s["image"] for s in rom.get("sample_screenshots", [])
                        ],
                        "moby_metadata": extract_metadata_from_moby_rom(rom),
                    }.items()
                    if v
                }
            )
            for rom in matched_roms
        ]


class SlugToMobyId(TypedDict):
    id: int
    name: str


SLUG_TO_RA_ID: dict[str, SlugToMobyId] = {
    "3do": {"id": 43, "name": "3DO"},
    "cpc": {"id": 37, "name": "Amstrad CPC"},
    "acpc": {"id": 37, "name": "Amstrad CPC"},
    "apple2": {"id": 38, "name": "Apple II"},
    "appleii": {"id": 38, "name": "Apple II"},
    "arcade": {"id": 27, "name": "Arcade"},
    "arcadia-2001": {"id": 73, "name": "Arcadia 2001"},
    "arduboy": {"id": 71, "name": "Arduboy"},
    "atari-2600": {"id": 25, "name": "Atari 2600"},
    "atari2600": {"id": 25, "name": "Atari 2600"},  # IGDB
    "atari-7800": {"id": 51, "name": "Atari 7800"},
    "atari7800": {"id": 51, "name": "Atari 7800"},  # IGDB
    "atari-jaguar-cd": {"id": 77, "name": "Atari Jaguar CD"},
    "colecovision": {"id": 44, "name": "ColecoVision"},
    "dreamcast": {"id": 40, "name": "Dreamcast"},
    "dc": {"id": 40, "name": "Dreamcast"},  # IGDB
    "gameboy": {"id": 4, "name": "Game Boy"},
    "gb": {"id": 4, "name": "Game Boy"},  # IGDB
    "gameboy-advance": {"id": 5, "name": "Game Boy Advance"},
    "gba": {"id": 5, "name": "Game Boy Advance"},  # IGDB
    "gameboy-color": {"id": 6, "name": "Game Boy Color"},
    "gbc": {"id": 6, "name": "Game Boy Color"},  # IGDB
    "game-gear": {"id": 15, "name": "Game Gear"},
    "gamegear": {"id": 15, "name": "Game Gear"},  # IGDB
    "gamecube": {"id": 16, "name": "GameCube"},
    "ngc": {"id": 14, "name": "GameCube"},  # IGDB
    "genesis": {"id": 1, "name": "Genesis/Mega Drive"},
    "genesis-slash-megadrive": {"id": 16, "name": "Genesis/Mega Drive"},
    "intellivision": {"id": 45, "name": "Intellivision"},
    "jaguar": {"id": 17, "name": "Jaguar"},
    "lynx": {"id": 13, "name": "Lynx"},
    "msx": {"id": 29, "name": "MSX"},
    "mega-duck-slash-cougar-boy": {"id": 69, "name": "Mega Duck/Cougar Boy"},
    "nes": {"id": 7, "name": "NES"},
    "famicom": {"id": 7, "name": "NES"},
    "neo-geo-cd": {"id": 56, "name": "Neo Geo CD"},
    "neo-geo-pocket": {"id": 14, "name": "Neo Geo Pocket"},
    "neo-geo-pocket-color": {"id": 14, "name": "Neo Geo Pocket Color"},
    "n64": {"id": 2, "name": "Nintendo 64"},
    "nintendo-ds": {"id": 18, "name": "Nintendo DS"},
    "nds": {"id": 18, "name": "Nintendo DS"},  # IGDB
    "nintendo-dsi": {"id": 78, "name": "Nintendo DSi"},
    "odyssey-2": {"id": 23, "name": "Odyssey 2"},
    "pc-8000": {"id": 47, "name": "PC-8000"},
    "pc-8800-series": {"id": 47, "name": "PC-8800 Series"},  # IGDB
    "pc-fx": {"id": 49, "name": "PC-FX"},
    "psp": {"id": 41, "name": "PSP"},
    "playstation": {"id": 12, "name": "PlayStation"},
    "ps": {"id": 12, "name": "PlayStation"},  # IGDB
    "ps2": {"id": 21, "name": "PlayStation 2"},
    "pokemon-mini": {"id": 24, "name": "Pokémon Mini"},
    "saturn": {"id": 39, "name": "Sega Saturn"},
    "sega-32x": {"id": 10, "name": "SEGA 32X"},
    "sega32": {"id": 10, "name": "SEGA 32X"},  # IGDB
    "sega-cd": {"id": 9, "name": "SEGA CD"},
    "segacd": {"id": 9, "name": "SEGA CD"},  # IGDB
    "sega-master-system": {"id": 11, "name": "SEGA Master System"},
    "sms": {"id": 11, "name": "SEGA Master System"},  # IGDB
    "sg-1000": {"id": 33, "name": "SG-1000"},
    "snes": {"id": 3, "name": "SNES"},
    "turbografx-cd": {"id": 76, "name": "TurboGrafx CD"},
    "turbografx-16-slash-pc-engine-cd": {"id": 76, "name": "TurboGrafx CD"},
    "turbo-grafx": {"id": 8, "name": "TurboGrafx-16"},
    "turbografx16--1": {"id": 8, "name": "TurboGrafx-16"},  # IGDB
    "vectrex": {"id": 26, "name": "Vectrex"},
    "virtual-boy": {"id": 28, "name": "Virtual Boy"},
    "virtualboy": {"id": 28, "name": "Virtual Boy"},
    "watara-slash-quickshot-supervision": {
        "id": 63,
        "name": "Watara/QuickShot Supervision",
    },
    "wonderswan": {"id": 53, "name": "WonderSwan"},
    "wonderswan-color": {"id": 53, "name": "WonderSwan Color"},
}

# Reverse lookup
MOBY_ID_TO_SLUG = {v["id"]: k for k, v in SLUG_TO_RA_ID.items()}
