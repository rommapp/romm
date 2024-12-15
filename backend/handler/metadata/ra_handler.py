import asyncio
import http
from typing import Final, NotRequired, TypedDict

import httpx
import yarl
from config import RETROACHIEVEMENTS_API_KEY, RETROACHIEVEMENTS_USERNAME
from fastapi import HTTPException, status
from logger.logger import log
from utils.context import ctx_httpx_client

from .base_hander import MetadataHandler

# Used to display the Mobygames API status in the frontend
RETROACHIEVEMENTS_API_ENABLED: Final = bool(RETROACHIEVEMENTS_API_KEY) and bool(
    RETROACHIEVEMENTS_USERNAME
)


class RAGamesPlatform(TypedDict):
    slug: str
    ra_id: int | None
    name: NotRequired[str]


class RAGameRom(TypedDict):
    ra_id: int | None


class RetroAchievementsHandler(MetadataHandler):
    def __init__(self) -> None:
        self.platform_url = "https://retroachievements.org/API/API_GetGameList.php"
        self.games_url = "https://api.mobygames.com/v1/games"

    async def _request(self, url: str, timeout: int = 120) -> dict:
        httpx_client = ctx_httpx_client.get()
        authorized_url = yarl.URL(url)
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

    async def _search_rom(self, md5_hash: str, platform_ra_id: int) -> dict | None:

        if not platform_ra_id:
            return None

        url = yarl.URL(self.platform_url).with_query(
            i=[platform_ra_id],
            h=["1"],
            f=["1"],
            z=[RETROACHIEVEMENTS_USERNAME],
            y=[RETROACHIEVEMENTS_API_KEY],
        )

        roms = await self._request(str(url))
        for rom in roms:
            if md5_hash in rom["Hashes"]:
                return rom

        return None

    def get_platform(self, slug: str) -> RAGamesPlatform:
        platform = SLUG_TO_RA_ID.get(slug.lower(), None)

        if not platform:
            return RAGamesPlatform(ra_id=None, slug=slug)

        return RAGamesPlatform(
            ra_id=platform["id"],
            slug=slug,
            name=platform["name"],
        )

    async def get_rom(self, md5_hash: str, platform_ra_id: int) -> RAGameRom:

        if not platform_ra_id:
            return RAGameRom(ra_id=None)

        fallback_rom = RAGameRom(ra_id=None)
        res = await self._search_rom(md5_hash, platform_ra_id)

        if not res:
            return fallback_rom

        return RAGameRom(
            {
                "ra_id": res["ID"],
            }
        )  # type: ignore[misc]


class SlugToRAId(TypedDict):
    id: int
    name: str


SLUG_TO_RA_ID: dict[str, SlugToRAId] = {
    # "3do": {"id": 43, "name": "3DO"},
    "cpc": {"id": 37, "name": "Amstrad CPC"},
    "acpc": {"id": 37, "name": "Amstrad CPC"},
    "apple2": {"id": 38, "name": "Apple II"},
    "appleii": {"id": 38, "name": "Apple II"},
    # "arcade": {"id": 27, "name": "Arcade"},
    "arcadia-2001": {"id": 73, "name": "Arcadia 2001"},
    # "arduboy": {"id": 71, "name": "Arduboy"},
    "atari-2600": {"id": 25, "name": "Atari 2600"},
    "atari2600": {"id": 25, "name": "Atari 2600"},  # IGDB
    "atari-7800": {"id": 51, "name": "Atari 7800"},
    "atari7800": {"id": 51, "name": "Atari 7800"},  # IGDB
    # "atari-jaguar-cd": {"id": 77, "name": "Atari Jaguar CD"},
    "colecovision": {"id": 44, "name": "ColecoVision"},
    # "dreamcast": {"id": 40, "name": "Dreamcast"},
    "dc": {"id": 40, "name": "Dreamcast"},  # IGDB
    "gameboy": {"id": 4, "name": "Game Boy"},
    "gb": {"id": 4, "name": "Game Boy"},  # IGDB
    "gameboy-advance": {"id": 5, "name": "Game Boy Advance"},
    "gba": {"id": 5, "name": "Game Boy Advance"},  # IGDB
    "gameboy-color": {"id": 6, "name": "Game Boy Color"},
    "gbc": {"id": 6, "name": "Game Boy Color"},  # IGDB
    "game-gear": {"id": 15, "name": "Game Gear"},
    "gamegear": {"id": 15, "name": "Game Gear"},  # IGDB
    # "gamecube": {"id": 16, "name": "GameCube"},
    # "ngc": {"id": 14, "name": "GameCube"},  # IGDB
    "genesis": {"id": 1, "name": "Genesis/Mega Drive"},
    "genesis-slash-megadrive": {"id": 16, "name": "Genesis/Mega Drive"},
    "intellivision": {"id": 45, "name": "Intellivision"},
    "jaguar": {"id": 17, "name": "Jaguar"},
    "lynx": {"id": 13, "name": "Lynx"},
    "msx": {"id": 29, "name": "MSX"},
    "mega-duck-slash-cougar-boy": {"id": 69, "name": "Mega Duck/Cougar Boy"},
    # "nes": {"id": 7, "name": "NES"},
    # "famicom": {"id": 7, "name": "NES"},
    # "neo-geo-cd": {"id": 56, "name": "Neo Geo CD"},
    "neo-geo-pocket": {"id": 14, "name": "Neo Geo Pocket"},
    "neo-geo-pocket-color": {"id": 14, "name": "Neo Geo Pocket Color"},
    "n64": {"id": 2, "name": "Nintendo 64"},
    # "nintendo-ds": {"id": 18, "name": "Nintendo DS"},
    # "nds": {"id": 18, "name": "Nintendo DS"},  # IGDB
    "nintendo-dsi": {"id": 78, "name": "Nintendo DSi"},
    "odyssey-2": {"id": 23, "name": "Odyssey 2"},
    "pc-8000": {"id": 47, "name": "PC-8000"},
    "pc-8800-series": {"id": 47, "name": "PC-8800 Series"},  # IGDB
    "pc-fx": {"id": 49, "name": "PC-FX"},
    # "psp": {"id": 41, "name": "PSP"},
    # "playstation": {"id": 12, "name": "PlayStation"},
    # "ps": {"id": 12, "name": "PlayStation"},  # IGDB
    # "ps2": {"id": 21, "name": "PlayStation 2"},
    "pokemon-mini": {"id": 24, "name": "Pokémon Mini"},
    # "saturn": {"id": 39, "name": "Sega Saturn"},
    "sega-32x": {"id": 10, "name": "SEGA 32X"},
    "sega32": {"id": 10, "name": "SEGA 32X"},  # IGDB
    # "sega-cd": {"id": 9, "name": "SEGA CD"},
    # "segacd": {"id": 9, "name": "SEGA CD"},  # IGDB
    "sega-master-system": {"id": 11, "name": "SEGA Master System"},
    "sms": {"id": 11, "name": "SEGA Master System"},  # IGDB
    "sg-1000": {"id": 33, "name": "SG-1000"},
    "snes": {"id": 3, "name": "SNES"},
    # "turbografx-cd": {"id": 76, "name": "TurboGrafx CD"},
    # "turbografx-16-slash-pc-engine-cd": {"id": 76, "name": "TurboGrafx CD"},
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
RA_ID_TO_SLUG = {v["id"]: k for k, v in SLUG_TO_RA_ID.items()}
