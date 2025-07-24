import json
import os
import time
from datetime import datetime
from typing import Final, NotRequired, TypedDict

import pydash
from adapters.services.retroachievements import RetroAchievementsService
from adapters.services.retroachievements_types import (
    RAGameExtendedDetails,
    RAGameListItem,
)
from config import (
    REFRESH_RETROACHIEVEMENTS_CACHE_DAYS,
    RETROACHIEVEMENTS_API_KEY,
)
from handler.filesystem import fs_resource_handler
from models.rom import Rom

from .base_hander import BaseRom, MetadataHandler

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
    first_release_date: int | None
    genres: list[str]
    companies: list[str]
    achievements: list[RAGameRomAchievement]


class RAGameRom(BaseRom):
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


def extract_metadata_from_rom_details(
    rom: Rom, rom_details: RAGameExtendedDetails
) -> RAMetadata:
    def parse_release_timestamp():
        release_date_str = rom_details.get("Released")
        if not release_date_str:
            return None

        try:
            # Extract date part (assuming format: "YYYY-MM-DD [additional info]")
            parsed_date = datetime.strptime(release_date_str.split()[0], "%Y-%m-%d")
            return int(parsed_date.timestamp())
        except (AttributeError, ValueError, IndexError):
            return None

    return RAMetadata(
        first_release_date=parse_release_timestamp(),
        genres=pydash.compact([rom_details.get("Genre", None)]),
        companies=pydash.compact(
            [rom_details.get("Publisher", None), rom_details.get("Developer", None)]
        ),
        achievements=[
            RAGameRomAchievement(
                ra_id=achievement.get("ID", None),
                title=achievement.get("Title", ""),
                description=achievement.get("Description", ""),
                points=achievement.get("Points", None),
                num_awarded=achievement.get("NumAwarded", None),
                num_awarded_hardcore=achievement.get("NumAwardedHardcore", None),
                badge_id=achievement.get("BadgeName", ""),
                badge_url_lock=f"https://media.retroachievements.org/Badge/{achievement.get('BadgeName', '')}_lock.png",
                badge_path_lock=f"{fs_resource_handler.get_ra_badges_path(rom.platform.id, rom.id)}/{achievement.get('BadgeName', '')}_lock.png",
                badge_url=f"https://media.retroachievements.org/Badge/{achievement.get('BadgeName', '')}.png",
                badge_path=f"{fs_resource_handler.get_ra_badges_path(rom.platform.id, rom.id)}/{achievement.get('BadgeName', '')}.png",
                display_order=achievement.get("DisplayOrder", None),
                type=achievement.get("type", ""),
            )
            for achievement in rom_details.get("Achievements", {}).values()
        ],
    )


class RAHandler(MetadataHandler):
    def __init__(self) -> None:
        self.ra_service = RetroAchievementsService()
        self.HASHES_FILE_NAME = "ra_hashes.json"

    def _get_hashes_file_path(self, platform_id: int) -> str:
        platform_resources_path = fs_resource_handler.get_platform_resources_path(
            platform_id
        )
        return os.path.join(platform_resources_path, self.HASHES_FILE_NAME)

    async def _exists_cache_file(self, platform_id: int) -> bool:
        return await fs_resource_handler.file_exists(
            self._get_hashes_file_path(platform_id)
        )

    async def _days_since_last_cache_file_update(self, platform_id: int) -> int:
        file_path = self._get_hashes_file_path(platform_id)
        if not await fs_resource_handler.file_exists(file_path):
            return REFRESH_RETROACHIEVEMENTS_CACHE_DAYS + 1

        full_path = fs_resource_handler.validate_path(file_path)
        return int((time.time() - os.path.getmtime(full_path)) / (24 * 3600))

    async def _search_rom(self, rom: Rom, ra_hash: str) -> RAGameListItem | None:
        if not rom.platform.ra_id:
            return None

        # Fetch all hashes for specific platform
        roms: list[RAGameListItem]
        if (
            REFRESH_RETROACHIEVEMENTS_CACHE_DAYS
            <= await self._days_since_last_cache_file_update(rom.platform.id)
            or not await self._exists_cache_file(rom.platform.id)
        ):
            # Write the roms result to a JSON file if older than REFRESH_RETROACHIEVEMENTS_CACHE_DAYS days
            roms = await self.ra_service.get_game_list(
                system_id=rom.platform.ra_id,
                only_games_with_achievements=True,
                include_hashes=True,
            )

            platform_resources_path = fs_resource_handler.get_platform_resources_path(
                rom.platform.id
            )

            json_file = json.dumps(roms, indent=4)
            await fs_resource_handler.write_file(
                json_file.encode("utf-8"),
                platform_resources_path,
                self.HASHES_FILE_NAME,
            )
        else:
            # Read the roms result from the JSON file
            json_file_bytes = await fs_resource_handler.read_file(
                self._get_hashes_file_path(rom.platform.id)
            )
            roms = json.loads(json_file_bytes.decode("utf-8"))

        for r in roms:
            if ra_hash in r.get("Hashes", ()):
                return r

        return None

    def get_platform(self, slug: str) -> RAGamesPlatform:
        platform = RA_PLATFORM_LIST.get(slug.lower(), None)

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
                ra_id=rom_details["ID"],
                name=rom_details.get("Title", ""),
                url_cover=(
                    f"https://retroachievements.org{rom_details['ImageTitle']}"
                    if rom_details.get("ImageTitle")
                    else ""
                ),
                url_manual=rom_details.get("GuideURL") or "",
                url_screenshots=pydash.compact(
                    [
                        (
                            f"https://retroachievements.org{rom_details['ImageIngame']}"
                            if rom_details.get("ImageIngame")
                            else None
                        )
                    ]
                ),
                ra_metadata=extract_metadata_from_rom_details(rom, rom_details),
            )
        except KeyError:
            return RAGameRom(ra_id=None)

    async def get_rom_by_id(self, rom: Rom, ra_id: int) -> RAGameRom:
        if not ra_id:
            return RAGameRom(ra_id=None)

        try:
            rom_details = await self.ra_service.get_game_extended_details(ra_id)
            return RAGameRom(
                ra_id=rom_details["ID"],
                name=rom_details.get("Title", ""),
                url_cover=(
                    f"https://media.retroachievements.org{rom_details['ImageTitle']}"
                    if rom_details.get("ImageTitle")
                    else ""
                ),
                url_manual=rom_details.get("GuideURL") or "",
                url_screenshots=pydash.compact(
                    [
                        (
                            f"https://media.retroachievements.org{rom_details['ImageIngame']}"
                            if rom_details.get("ImageIngame")
                            else None
                        )
                    ]
                ),
                ra_metadata=extract_metadata_from_rom_details(rom, rom_details),
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


RA_PLATFORM_LIST: dict[str, SlugToRAId] = {
    "3do": {"id": 43, "name": "3DO"},
    "acpc": {"id": 37, "name": "Amstrad CPC"},
    "appleii": {"id": 38, "name": "Apple II"},
    "arcade": {"id": 27, "name": "Arcade"},
    "arcadia-2001": {"id": 73, "name": "Arcadia 2001"},
    "arduboy": {"id": 71, "name": "Arduboy"},
    "atari2600": {"id": 25, "name": "Atari 2600"},
    "atari7800": {"id": 51, "name": "Atari 7800"},
    "atari-jaguar-cd": {"id": 77, "name": "Atari Jaguar CD"},
    "colecovision": {"id": 44, "name": "ColecoVision"},
    "dc": {"id": 40, "name": "Dreamcast"},
    "elektor": {"id": 75, "name": "Elektor"},
    "fairchild-channel-f": {"id": 57, "name": "Fairchild Channel F"},
    "gb": {"id": 4, "name": "Game Boy"},
    "gba": {"id": 5, "name": "Game Boy Advance"},
    "gbc": {"id": 6, "name": "Game Boy Color"},
    "gamegear": {"id": 15, "name": "Game Gear"},
    "ngc": {"id": 16, "name": "GameCube"},
    "genesis": {"id": 1, "name": "Genesis/Mega Drive"},
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
    "nds": {"id": 18, "name": "Nintendo DS"},
    "nintendo-dsi": {"id": 78, "name": "Nintendo DSi"},
    "odyssey-2": {"id": 23, "name": "Odyssey 2"},
    "pc-8800-series": {"id": 47, "name": "PC-8800 Series"},
    "pc-fx": {"id": 49, "name": "PC-FX"},
    "psp": {"id": 41, "name": "PSP"},
    "psx": {"id": 12, "name": "PlayStation"},
    "ps2": {"id": 21, "name": "PlayStation 2"},
    "pokemon-mini": {"id": 24, "name": "Pokémon Mini"},
    "saturn": {"id": 39, "name": "Sega Saturn"},
    "sega32": {"id": 10, "name": "SEGA 32X"},
    "segacd": {"id": 9, "name": "SEGA CD"},
    "sms": {"id": 11, "name": "SEGA Master System"},
    "sg1000": {"id": 33, "name": "SG-1000"},
    "snes": {"id": 3, "name": "SNES"},
    "sfam": {"id": 3, "name": "Super Famicom"},
    "turbografx-cd": {"id": 76, "name": "TurboGrafx CD"},
    "tg16": {"id": 8, "name": "TurboGrafx-16"},
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
RA_ID_TO_SLUG = {v["id"]: k for k, v in RA_PLATFORM_LIST.items()}
