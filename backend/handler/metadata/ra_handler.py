import asyncio
import http
import json
import os
import time
from typing import Final, NotRequired, TypedDict

import httpx
import yarl
from adapters.services.retroachievements import RetroAchievementsService
from adapters.services.retroachievements_types import RAGameListItem
from anyio import open_file
from config import (
    REFRESH_RETROACHIEVEMENTS_CACHE_DAYS,
    RESOURCES_BASE_PATH,
    RETROACHIEVEMENTS_API_KEY,
)
from fastapi import HTTPException, status
from handler.filesystem import fs_resource_handler
from logger.logger import log
from models.rom import Rom
from utils.context import ctx_httpx_client

from .base_hander import MetadataHandler

# Used to display the Retroachievements API status in the frontend
RA_API_ENABLED: Final = bool(RETROACHIEVEMENTS_API_KEY)


class RAGamesPlatform(TypedDict):
    slug: str
    ra_id: int | None
    name: NotRequired[str]


class RAGameRomAchievement(TypedDict):
    ra_id: int | None
    title: str | None
    description: str | None
    points: int | None
    num_awarded: int | None
    num_awarded_hardcore: int | None
    badge_id: str | None
    badge_url_lock: str | None
    badge_path_lock: str | None
    badge_url: str | None
    badge_path: str | None
    display_order: int | None
    type: str | None


class RAMetadata(TypedDict):
    achievements: list[RAGameRomAchievement]


class RAGameRom(TypedDict):
    ra_id: int | None
    ra_metadata: NotRequired[RAMetadata]


class EarnedAchievement(TypedDict):
    id: str
    date: str
    date_hardcore: NotRequired[str]


class RAUserGameProgression(TypedDict):
    rom_ra_id: int | None
    max_possible: int | None
    num_awarded: int | None
    num_awarded_hardcore: int | None
    earned_achievements: list[EarnedAchievement]


class RAUserProgression(TypedDict):
    total: int
    results: list[RAUserGameProgression]


class RAHandler(MetadataHandler):
    def __init__(self) -> None:
        self.ra_service = RetroAchievementsService()
        self.HASHES_FILE_NAME = "ra_hashes.json"

    def _get_hashes_file_path(self, platform_id: int) -> str:
        return os.path.join(
            RESOURCES_BASE_PATH,
            "roms",
            str(platform_id),
            self.HASHES_FILE_NAME,
        )

    def _exists_cache_file(self, platform_id: int) -> bool:
        return os.path.exists(self._get_hashes_file_path(platform_id))

    def _days_since_last_cache_file_update(self, platform_id: int) -> int:
        file_path = self._get_hashes_file_path(platform_id)
        return (
            0
            if not os.path.exists(file_path)
            else int((time.time() - os.path.getmtime(file_path)) / (24 * 3600))
        )

    async def _request(self, url: str, request_timeout: int = 120) -> dict:
        httpx_client = ctx_httpx_client.get()
        authorized_url = yarl.URL(url)
        masked_url = authorized_url.with_query(
            self._mask_sensitive_values(dict(authorized_url.query))
        )
        log.debug(
            "API request: URL=%s, Timeout=%s",
            masked_url,
            request_timeout,
        )
        try:
            res = await httpx_client.get(str(authorized_url), timeout=request_timeout)
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
            log.debug(
                "API request: URL=%s, Timeout=%s",
                url,
                request_timeout,
            )
            res = await httpx_client.get(url, timeout=request_timeout)
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

    async def _search_rom(self, rom: Rom, ra_hash: str) -> RAGameListItem | None:
        if not rom.platform.ra_id:
            return None

        # Fetch all hashes for specific platform
        roms: list[RAGameListItem]
        if (
            REFRESH_RETROACHIEVEMENTS_CACHE_DAYS
            <= self._days_since_last_cache_file_update(rom.platform.id)
            or not self._exists_cache_file(rom.platform.id)
        ):
            # Write the roms result to a JSON file if older than REFRESH_RETROACHIEVEMENTS_CACHE_DAYS days
            roms = await self.ra_service.get_game_list(
                system_id=rom.platform.ra_id,
                only_games_with_achievements=True,
                include_hashes=True,
            )
            os.makedirs(
                os.path.dirname(self._get_hashes_file_path(rom.platform.id)),
                exist_ok=True,
            )
            async with await open_file(
                self._get_hashes_file_path(rom.platform.id),
                "w",
                encoding="utf-8",
            ) as json_file:
                await json_file.write(json.dumps(roms, indent=4))
        else:
            # Read the roms result from the JSON file
            async with await open_file(
                self._get_hashes_file_path(rom.platform.id),
                "r",
                encoding="utf-8",
            ) as json_file:
                roms = json.loads(await json_file.read())

        for r in roms:
            if ra_hash in r.get("Hashes", ()):
                return r

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

    async def get_rom(self, rom: Rom, ra_hash: str) -> RAGameRom:
        if not rom.platform.ra_id or not ra_hash:
            return RAGameRom(ra_id=None)

        ra_game_list_item = await self._search_rom(rom, ra_hash)

        if not ra_game_list_item:
            return RAGameRom(ra_id=None)

        try:
            rom_details = await self.ra_service.get_game_extended_details(
                ra_game_list_item["ID"]
            )
            return RAGameRom(
                ra_id=ra_game_list_item["ID"],
                ra_metadata=RAMetadata(
                    achievements=[
                        RAGameRomAchievement(
                            ra_id=achievement.get("ID", None),
                            title=achievement.get("Title", ""),
                            description=achievement.get("Description", ""),
                            points=achievement.get("Points", None),
                            num_awarded=achievement.get("NumAwarded", None),
                            num_awarded_hardcore=achievement.get(
                                "NumAwardedHardcore", None
                            ),
                            badge_id=achievement.get("BadgeName", ""),
                            badge_url_lock=f"https://media.retroachievements.org/Badge/{achievement.get('BadgeName', '')}_lock.png",
                            badge_path_lock=f"{fs_resource_handler.get_ra_badges_path(rom.platform.id, rom.id)}/{achievement.get('BadgeName', '')}",
                            badge_url=f"https://media.retroachievements.org/Badge/{achievement.get('BadgeName', '')}.png",
                            badge_path=f"{fs_resource_handler.get_ra_badges_path(rom.platform.id, rom.id)}/{achievement.get('BadgeName', '')}.png",
                            display_order=achievement.get("DisplayOrder", None),
                            type=achievement.get("type", ""),
                        )
                        for achievement in rom_details.get("Achievements", {}).values()
                    ]
                ),
            )
        except KeyError:
            return RAGameRom(ra_id=None)

    async def get_rom_by_id(self, ra_id: int) -> RAGameRom:
        if not ra_id:
            return RAGameRom(ra_id=None)

        try:
            rom_details = await self.ra_service.get_game_extended_details(ra_id)
            return RAGameRom(
                ra_id=ra_id,
                ra_metadata=RAMetadata(
                    achievements=[
                        RAGameRomAchievement(
                            ra_id=achievement.get("ID", None),
                            title=achievement.get("Title", ""),
                            description=achievement.get("Description", ""),
                            points=achievement.get("Points", None),
                            num_awarded=achievement.get("NumAwarded", None),
                            num_awarded_hardcore=achievement.get(
                                "NumAwardedHardcore", None
                            ),
                            badge_id=achievement.get("BadgeName", ""),
                            badge_url_lock=f"https://media.retroachievements.org/Badge/{achievement.get('BadgeName', '')}_lock.png",
                            badge_path_lock=f"{fs_resource_handler.get_ra_badges_path(0, 0)}/{achievement.get('BadgeName', '')}_lock.png",
                            badge_url=f"https://media.retroachievements.org/Badge/{achievement.get('BadgeName', '')}.png",
                            badge_path=f"{fs_resource_handler.get_ra_badges_path(0, 0)}/{achievement.get('BadgeName', '')}.png",
                            display_order=achievement.get("DisplayOrder", None),
                            type=achievement.get("type", ""),
                        )
                        for achievement in rom_details.get("Achievements", {}).values()
                    ]
                ),
            )
        except KeyError:
            return RAGameRom(ra_id=None)

    async def get_user_progression(self, username: str) -> RAUserProgression:
        game_progressions: list[RAUserGameProgression] = []

        async for rom in self.ra_service.iter_user_completion_progress(username):
            rom_game_id = rom.get("GameID")
            earned_achievements: list[EarnedAchievement] = []
            if rom_game_id:
                result = await self.ra_service.get_user_game_progress(
                    username=username,
                    game_id=rom_game_id,
                )
                for achievement in result.get("Achievements", {}).values():
                    badge_name = achievement.get("BadgeName")
                    date_earned = achievement.get("DateEarned")
                    date_earned_hardcore = achievement.get("DateEarnedHardcore")
                    if badge_name and date_earned:
                        earned_achievement = EarnedAchievement(
                            id=badge_name,
                            date=date_earned,
                        )
                        if date_earned_hardcore:
                            earned_achievement["date_hardcore"] = date_earned_hardcore
                        earned_achievements.append(earned_achievement)

            game_progressions.append(
                RAUserGameProgression(
                    rom_ra_id=rom_game_id,
                    max_possible=rom.get("MaxPossible", None),
                    num_awarded=rom.get("NumAwarded", None),
                    num_awarded_hardcore=rom.get("NumAwardedHardcore", None),
                    earned_achievements=earned_achievements,
                )
            )

        return RAUserProgression(
            total=len(game_progressions),
            results=game_progressions,
        )


class SlugToRAId(TypedDict):
    id: int
    name: str


SLUG_TO_RA_ID: dict[str, SlugToRAId] = {
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
    "elektor": {"id": 75, "name": "Elektor"},
    "fairchild-channel-f": {"id": 57, "name": "Fairchild Channel F"},
    "gameboy": {"id": 4, "name": "Game Boy"},
    "gb": {"id": 4, "name": "Game Boy"},  # IGDB
    "gameboy-advance": {"id": 5, "name": "Game Boy Advance"},
    "gba": {"id": 5, "name": "Game Boy Advance"},  # IGDB
    "gameboy-color": {"id": 6, "name": "Game Boy Color"},
    "gbc": {"id": 6, "name": "Game Boy Color"},  # IGDB
    "game-gear": {"id": 15, "name": "Game Gear"},
    "gamegear": {"id": 15, "name": "Game Gear"},  # IGDB
    "gamecube": {"id": 16, "name": "GameCube"},
    "ngc": {"id": 16, "name": "GameCube"},  # IGDB
    "genesis": {"id": 1, "name": "Genesis/Mega Drive"},
    "genesis-slash-megadrive": {"id": 1, "name": "Genesis/Mega Drive"},
    "intellivision": {"id": 45, "name": "Intellivision"},
    "interton-vc-4000": {"id": 74, "name": "Interton VC 4000"},
    "jaguar": {"id": 17, "name": "Jaguar"},
    "lynx": {"id": 13, "name": "Lynx"},
    "msx": {"id": 29, "name": "MSX"},
    "mega-duck-slash-cougar-boy": {"id": 69, "name": "Mega Duck/Cougar Boy"},
    "nes": {"id": 7, "name": "NES"},
    "famicom": {"id": 7, "name": "Family Computer"},
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
    "sfam": {"id": 3, "name": "Super Famicom"},  # IGDB
    "turbografx-cd": {"id": 76, "name": "TurboGrafx CD"},
    "turbografx-16-slash-pc-engine-cd": {"id": 76, "name": "TurboGrafx CD"},
    "turbo-grafx": {"id": 8, "name": "TurboGrafx-16"},
    "turbografx16--1": {"id": 8, "name": "TurboGrafx-16"},  # IGDB
    "uzebox": {"id": 80, "name": "Uzebox"},
    "vectrex": {"id": 46, "name": "Vectrex"},
    "virtual-boy": {"id": 28, "name": "Virtual Boy"},
    "virtualboy": {"id": 28, "name": "Virtual Boy"},
    "wasm-4": {"id": 72, "name": "WASM-4"},
    "watara-slash-quickshot-supervision": {
        "id": 63,
        "name": "Watara/QuickShot Supervision",
    },
    "win": {"id": 102, "name": "Windows"},
    "wonderswan": {"id": 53, "name": "WonderSwan"},
    "wonderswan-color": {"id": 53, "name": "WonderSwan Color"},
}

# Reverse lookup
RA_ID_TO_SLUG = {v["id"]: k for k, v in SLUG_TO_RA_ID.items()}
