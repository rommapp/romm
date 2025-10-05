import json
import os
import re
import time
from datetime import datetime
from typing import NotRequired, TypedDict

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
from logger.logger import log
from models.rom import Rom

from .base_handler import BaseRom, MetadataHandler
from .base_handler import UniversalPlatformSlug as UPS

# Regex to detect RetroAchievements ID tags in filenames like (ra-12345)
RA_TAG_REGEX = re.compile(r"\(ra-(\d+)\)", re.IGNORECASE)


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
    most_recent_awarded_date: NotRequired[str | None]
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

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(RETROACHIEVEMENTS_API_KEY)

    async def heartbeat(self) -> bool:
        if not self.is_enabled():
            return False

        try:
            response = await self.ra_service.get_achievement_of_the_week()
        except Exception as e:
            log.error("Error checking RetroAchievements API: %s", e)
            return False

        return bool(response)

    @staticmethod
    def extract_ra_id_from_filename(fs_name: str) -> int | None:
        """Extract RetroAchievements ID from filename tag like (ra-12345)."""
        match = RA_TAG_REGEX.search(fs_name)
        if match:
            return int(match.group(1))
        return None

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

        ra_hash_lower = ra_hash.lower()
        for r in roms:
            if any(ra_hash_lower == h.lower() for h in r.get("Hashes", ())):
                return r

        return None

    def get_platform(self, slug: str) -> RAGamesPlatform:
        if slug not in RA_PLATFORM_LIST:
            return RAGamesPlatform(ra_id=None, slug=slug)

        platform = RA_PLATFORM_LIST[UPS(slug)]

        return RAGamesPlatform(
            ra_id=platform["id"],
            slug=slug,
            name=platform["name"],
        )

    async def get_rom(self, rom: Rom, ra_hash: str) -> RAGameRom:
        if not rom.platform.ra_id:
            return RAGameRom(ra_id=None)

        # Check for RetroAchievements ID tag in filename first
        ra_id_from_tag = self.extract_ra_id_from_filename(rom.fs_name)
        if ra_id_from_tag:
            log.debug(f"Found RetroAchievements ID tag in filename: {ra_id_from_tag}")
            rom_by_id = await self.get_rom_by_id(rom=rom, ra_id=ra_id_from_tag)
            if rom_by_id["ra_id"]:
                log.debug(
                    f"Successfully matched ROM by RetroAchievements ID tag: {rom.fs_name} -> {ra_id_from_tag}"
                )
                return rom_by_id
            else:
                log.warning(
                    f"RetroAchievements ID {ra_id_from_tag} from filename tag not found in RetroAchievements"
                )

        if not ra_hash:
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

    async def get_user_progression(
        self,
        username: str,
        current_progression: RAUserProgression | None = None,
    ) -> RAUserProgression:
        """Retrieves the user's RetroAchievements progression.

        If `current_progression` is provided, it will only incrementally update the
        progression based on new achievements since the last check.
        """
        game_progressions: list[RAUserGameProgression] = []
        current_progression_by_game_id: dict[int | None, RAUserGameProgression] = {}
        if current_progression:
            current_progression_by_game_id = {
                p["rom_ra_id"]: p for p in current_progression.get("results", [])
            }

        async for rom in self.ra_service.iter_user_completion_progress(username):
            rom_game_id = rom.get("GameID")

            # If we have current progression data, and number of awarded achievements and most
            # recent awarded date match, then we can skip fetching progression details.
            game_current_progression = current_progression_by_game_id.get(rom_game_id)
            if (
                game_current_progression
                and rom["NumAwarded"] == game_current_progression.get("num_awarded")
                and rom["NumAwardedHardcore"]
                == game_current_progression.get("num_awarded_hardcore")
                and rom["MostRecentAwardedDate"]
                == game_current_progression.get("most_recent_awarded_date")
            ):
                game_progressions.append(game_current_progression)
                continue

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
                    most_recent_awarded_date=rom.get("MostRecentAwardedDate", None),
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


RA_PLATFORM_LIST: dict[UPS, SlugToRAId] = {
    UPS._3DO: {"id": 43, "name": "3DO"},
    UPS.ACPC: {"id": 37, "name": "Amstrad CPC"},
    UPS.APPLEII: {"id": 38, "name": "Apple II"},
    UPS.ARCADE: {"id": 27, "name": "Arcade"},
    UPS.ARCADIA_2001: {"id": 73, "name": "Arcadia 2001"},
    UPS.ARDUBOY: {"id": 71, "name": "Arduboy"},
    UPS.ATARI2600: {"id": 25, "name": "Atari 2600"},
    UPS.ATARI7800: {"id": 51, "name": "Atari 7800"},
    UPS.ATARI_JAGUAR_CD: {"id": 77, "name": "Atari Jaguar CD"},
    UPS.COLECOVISION: {"id": 44, "name": "ColecoVision"},
    UPS.DC: {"id": 40, "name": "Dreamcast"},
    UPS.ELEKTOR: {"id": 75, "name": "Elektor"},
    UPS.FAIRCHILD_CHANNEL_F: {
        "id": 57,
        "name": "Fairchild Channel F",
    },
    UPS.GB: {"id": 4, "name": "Game Boy"},
    UPS.GBA: {"id": 5, "name": "Game Boy Advance"},
    UPS.GBC: {"id": 6, "name": "Game Boy Color"},
    UPS.GAMEGEAR: {"id": 15, "name": "Game Gear"},
    UPS.NGC: {"id": 16, "name": "GameCube"},
    UPS.GENESIS: {"id": 1, "name": "Genesis/Mega Drive"},
    UPS.INTELLIVISION: {"id": 45, "name": "Intellivision"},
    UPS.INTERTON_VC_4000: {"id": 74, "name": "Interton VC 4000"},
    UPS.JAGUAR: {"id": 17, "name": "Jaguar"},
    UPS.LYNX: {"id": 13, "name": "Lynx"},
    UPS.MSX: {"id": 29, "name": "MSX"},
    UPS.MEGA_DUCK_SLASH_COUGAR_BOY: {
        "id": 69,
        "name": "Mega Duck/Cougar Boy",
    },
    UPS.NES: {"id": 7, "name": "NES"},
    UPS.FAMICOM: {"id": 7, "name": "Family Computer"},
    UPS.NEO_GEO_CD: {"id": 56, "name": "Neo Geo CD"},
    UPS.NEO_GEO_POCKET: {"id": 14, "name": "Neo Geo Pocket"},
    UPS.NEO_GEO_POCKET_COLOR: {
        "id": 14,
        "name": "Neo Geo Pocket Color",
    },
    UPS.N64: {"id": 2, "name": "Nintendo 64"},
    UPS.NDS: {"id": 18, "name": "Nintendo DS"},
    UPS.NINTENDO_DSI: {"id": 78, "name": "Nintendo DSi"},
    UPS.ODYSSEY_2: {"id": 23, "name": "Odyssey 2"},
    UPS.PC_8800_SERIES: {"id": 47, "name": "PC-8800 Series"},
    UPS.PC_FX: {"id": 49, "name": "PC-FX"},
    UPS.PSP: {"id": 41, "name": "PSP"},
    UPS.PSX: {"id": 12, "name": "PlayStation"},
    UPS.PS2: {"id": 21, "name": "PlayStation 2"},
    UPS.POKEMON_MINI: {"id": 24, "name": "Pokémon Mini"},
    UPS.SATURN: {"id": 39, "name": "Sega Saturn"},
    UPS.SEGA32: {"id": 10, "name": "SEGA 32X"},
    UPS.SEGACD: {"id": 9, "name": "SEGA CD"},
    UPS.SMS: {"id": 11, "name": "SEGA Master System"},
    UPS.SG1000: {"id": 33, "name": "SG-1000"},
    UPS.SNES: {"id": 3, "name": "SNES"},
    UPS.SFAM: {"id": 3, "name": "Super Famicom"},
    UPS.TURBOGRAFX_CD: {"id": 76, "name": "TurboGrafx CD"},
    UPS.TG16: {"id": 8, "name": "TurboGrafx-16"},
    UPS.UZEBOX: {"id": 80, "name": "Uzebox"},
    UPS.VECTREX: {"id": 46, "name": "Vectrex"},
    UPS.VIRTUALBOY: {"id": 28, "name": "Virtual Boy"},
    UPS.WASM_4: {"id": 72, "name": "WASM-4"},
    UPS.SUPERVISION: {
        "id": 63,
        "name": "Watara/QuickShot Supervision",
    },
    UPS.WIN: {"id": 102, "name": "Windows"},
    UPS.WONDERSWAN: {"id": 53, "name": "WonderSwan"},
    UPS.WONDERSWAN_COLOR: {"id": 53, "name": "WonderSwan Color"},
}

# Reverse lookup
RA_ID_TO_SLUG = {v["id"]: k for k, v in RA_PLATFORM_LIST.items()}
