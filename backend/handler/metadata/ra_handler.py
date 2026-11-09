import json
import os
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Any, NotRequired, TypedDict, cast

import pydash
from anyio import Path as AnyioPath
from pydantic import Field

from adapters.services.provider_http import unavailable
from adapters.services.retroachievements import RetroAchievementsService
from adapters.services.retroachievements_types import (
    RAGameExtendedDetails,
)
from config import (
    REFRESH_RETROACHIEVEMENTS_CACHE_DAYS,
    RETROACHIEVEMENTS_API_KEY,
)
from handler.filesystem import fs_resource_handler
from logger.logger import log
from models.rom import Rom
from utils.arcade_platforms import ARCADE_SET_PLATFORMS, arcade_fallbacks
from utils.datetime import parse_utc_timestamp
from utils.platform_slugs import UniversalPlatformSlug as UPS
from utils.platform_slugs import fill_duplicate_slugs

from .base_handler import (
    BaseRom,
    MetadataHandler,
    provider_tag_regex,
    tag_id_from_filename,
)

# Regex to detect RetroAchievements ID tags in filenames like (ra-12345)
RA_TAG_REGEX = provider_tag_regex("ra")


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
    publishers: list[str]
    developers: list[str]
    achievements: list[RAGameRomAchievement]
    # The ROM's RA hash is one RetroAchievements lists for this game.
    hash_match: NotRequired[bool]
    # ImageIcon path from the API, e.g. /Images/047227.png. Not the game id.
    image_icon: NotRequired[str]
    # Title, in-game and box art. Same path shape. Empty string: asked, none.
    image_title: NotRequired[str]
    image_ingame: NotRequired[str]
    image_box_art: NotRequired[str]


class RAGameRom(BaseRom):
    ra_id: int | None
    ra_metadata: NotRequired[RAMetadata]


class EarnedAchievement(TypedDict):
    id: Annotated[
        str,
        Field(
            description="The badge name, which several achievements can share. Use `ra_id`.",
            deprecated=True,
        ),
    ]
    ra_id: NotRequired[int]
    date: str
    date_hardcore: NotRequired[str]


class RAUserGameProgression(TypedDict):
    rom_ra_id: int | None
    max_possible: int | None
    num_awarded: int | None
    num_awarded_hardcore: int | None
    most_recent_awarded_date: NotRequired[str | None]
    highest_award_kind: NotRequired[str | None]
    earned_achievements: list[EarnedAchievement]


class RAUserProgression(TypedDict):
    total: int
    results: list[RAUserGameProgression]


def extract_metadata_from_rom_details(
    rom: Rom, rom_details: RAGameExtendedDetails, hash_match: bool
) -> RAMetadata:
    def parse_release_timestamp() -> int | None:
        release_date_str = rom_details.get("Released")
        if not release_date_str:
            return None

        try:
            # "YYYY-MM-DD [additional info]"
            date_part = release_date_str.split()[0]
        except AttributeError, IndexError:
            return None
        return parse_utc_timestamp(date_part, ("%Y-%m-%d",))

    publishers = pydash.compact([rom_details.get("Publisher", None)])
    developers = pydash.compact([rom_details.get("Developer", None)])

    metadata = RAMetadata(
        first_release_date=parse_release_timestamp(),
        genres=pydash.compact([rom_details.get("Genre", None)]),
        companies=[*publishers, *developers],
        publishers=publishers,
        developers=developers,
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
        hash_match=hash_match,
    )
    # Local import: this module is loaded while the metadata package initializes.
    from handler.metadata.earned_achievements import ra_art_paths, ra_image_icon_path

    icon = ra_image_icon_path(rom_details.get("ImageIcon"))
    if icon:
        metadata["image_icon"] = icon
    art = ra_art_paths(rom_details)
    if art:
        if art["image_title"]:
            metadata["image_title"] = art["image_title"]
        if art["image_ingame"]:
            metadata["image_ingame"] = art["image_ingame"]
        if art["image_box_art"]:
            metadata["image_box_art"] = art["image_box_art"]
    return metadata


class RAHandler(MetadataHandler):
    def __init__(self) -> None:
        self.ra_service = RetroAchievementsService()
        self.HASHES_FILE_NAME = "ra_hashes_v3.json"
        # Parsed hash index per platform id, with the cache file mtime it came from.
        self._hash_indexes: dict[int, tuple[float, dict[str, int]]] = {}

    @classmethod
    def is_enabled(cls) -> bool:
        return bool(RETROACHIEVEMENTS_API_KEY)

    async def heartbeat(self) -> bool:
        async def probe() -> bool:
            return bool(await self.ra_service.get_achievement_of_the_week())

        return await self._heartbeat("RetroAchievements API", probe)

    @staticmethod
    def extract_ra_id_from_filename(fs_name: str) -> int | None:
        """Extract RetroAchievements ID from filename tag like (ra-12345)."""
        return tag_id_from_filename(RA_TAG_REGEX, fs_name)

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
        file_stat = await AnyioPath(str(full_path)).stat()
        return int((time.time() - file_stat.st_mtime) / (24 * 3600))

    async def _search_rom(self, rom: Rom, ra_hash: str) -> int | None:
        if not rom.platform.ra_id:
            return None

        # hash_index maps lowercase hash -> game ID for O(1) lookups
        hash_index: dict[str, int]
        if (
            REFRESH_RETROACHIEVEMENTS_CACHE_DAYS
            <= await self._days_since_last_cache_file_update(rom.platform.id)
            or not await self._exists_cache_file(rom.platform.id)
        ):
            # An RA match should mean a set exists, so skip games without one
            roms = await self.ra_service.get_game_list(
                system_id=rom.platform.ra_id,
                only_games_with_achievements=True,
                include_hashes=True,
            )
            # A failed request comes back as {}, which must not be cached as an
            # empty index for the whole refresh window.
            if not isinstance(roms, list):
                raise unavailable("RetroAchievements")

            hash_index = {h.lower(): r["ID"] for r in roms for h in r.get("Hashes", ())}

            platform_resources_path = fs_resource_handler.get_platform_resources_path(
                rom.platform.id
            )

            json_file = json.dumps(hash_index, indent=4)
            await fs_resource_handler.write_file(
                json_file.encode("utf-8"),
                platform_resources_path,
                self.HASHES_FILE_NAME,
            )
        else:
            file_path = self._get_hashes_file_path(rom.platform.id)
            full_path = fs_resource_handler.validate_path(file_path)
            mtime = (await AnyioPath(str(full_path)).stat()).st_mtime
            cached = self._hash_indexes.get(rom.platform.id)
            if cached and cached[0] == mtime:
                hash_index = cached[1]
            else:
                json_file_bytes = await fs_resource_handler.read_file(file_path)
                hash_index = json.loads(json_file_bytes.decode("utf-8"))
                self._hash_indexes[rom.platform.id] = (mtime, hash_index)

        return hash_index.get(ra_hash.lower())

    async def _hash_matches(self, rom: Rom, ra_hash: str | None, ra_id: int) -> bool:
        if not ra_hash:
            return False
        try:
            return await self._search_rom(rom, ra_hash) == ra_id
        except Exception as exc:
            # A failed check must not block the ID lookup, nor drop a match
            # already recorded for this game and hash.
            log.warning(f"Couldn't check the RetroAchievements hash list: {exc}")
            return (
                rom.ra_id == ra_id
                and rom.ra_hash == ra_hash
                and bool((rom.ra_metadata or {}).get("hash_match"))
            )

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
            rom_by_id = await self.get_rom_by_id(
                rom=rom, ra_id=ra_id_from_tag, ra_hash=ra_hash
            )
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

        ra_game_id = await self._search_rom(rom, ra_hash)

        if ra_game_id is None:
            return RAGameRom(ra_id=None)

        rom_details = await self.ra_service.get_game_extended_details(ra_game_id)
        # A failed request raises; None means RA retired the game the index named.
        if not rom_details:
            return RAGameRom(ra_id=None)

        try:
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
                ra_metadata=extract_metadata_from_rom_details(
                    rom, rom_details, hash_match=True
                ),
            )
        except KeyError:
            return RAGameRom(ra_id=None)

    async def get_rom_by_id(
        self, rom: Rom, ra_id: int, ra_hash: str | None = None
    ) -> RAGameRom:
        if not ra_id:
            return RAGameRom(ra_id=None)

        try:
            rom_details = await self.ra_service.get_game_extended_details(ra_id)
            if not rom_details:
                return RAGameRom(ra_id=None)
            game_id = rom_details["ID"]
            hash_match = await self._hash_matches(rom, ra_hash, ra_id)
            return RAGameRom(
                ra_id=game_id,
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
                ra_metadata=extract_metadata_from_rom_details(
                    rom, rom_details, hash_match=hash_match
                ),
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
            highest_award_kind = rom.get("HighestAwardKind", None)

            # If we have current progression data, and number of awarded achievements and most
            # recent awarded date match, then we can skip fetching progression details.
            game_current_progression = current_progression_by_game_id.get(rom_game_id)
            if (
                game_current_progression
                # Entries stored before `ra_id` existed are read again to gain it.
                and all(
                    "ra_id" in e
                    for e in game_current_progression.get("earned_achievements", [])
                )
                and rom["NumAwarded"] == game_current_progression.get("num_awarded")
                and rom["NumAwardedHardcore"]
                == game_current_progression.get("num_awarded_hardcore")
                and rom["MostRecentAwardedDate"]
                == game_current_progression.get("most_recent_awarded_date")
            ):
                # Always keep highest_award_kind up-to-date even for cached progressions
                if (
                    game_current_progression.get("highest_award_kind")
                    != highest_award_kind
                ):
                    game_current_progression = cast(
                        RAUserGameProgression,
                        {
                            **game_current_progression,
                            "highest_award_kind": highest_award_kind,
                        },
                    )
                game_progressions.append(game_current_progression)
                continue

            earned_achievements: list[EarnedAchievement] = []
            if rom_game_id:
                result = await self.ra_service.get_user_game_progress(
                    username=username,
                    game_id=rom_game_id,
                )
                achievements = result.get("Achievements", {}) if result else {}
                for achievement in achievements.values():
                    badge_name = achievement.get("BadgeName")
                    date_earned = achievement.get("DateEarned")
                    date_earned_hardcore = achievement.get("DateEarnedHardcore")
                    if badge_name and date_earned:
                        earned_achievement = EarnedAchievement(
                            id=badge_name,
                            date=date_earned,
                        )
                        if achievement.get("ID") is not None:
                            earned_achievement["ra_id"] = achievement["ID"]
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
                    highest_award_kind=highest_award_kind,
                    earned_achievements=earned_achievements,
                )
            )

        return RAUserProgression(
            total=len(game_progressions),
            results=game_progressions,
        )

    async def persist_missing_image_icons(self) -> dict[int, str]:
        """Save each library game's ImageIcon from the same reply as its screen art."""
        from handler.database import db_rom_handler

        sources = db_rom_handler.get_library_achievement_sources()
        platform_ids: list[int] = []
        seen_platforms: set[int] = set()
        for source in sources:
            ra_id = source.get("ra_id")
            platform_id = source.get("platform_id")
            if (
                isinstance(ra_id, int)
                and not isinstance(ra_id, bool)
                and isinstance(platform_id, int)
                and platform_id not in seen_platforms
            ):
                seen_platforms.add(platform_id)
                platform_ids.append(platform_id)
        cached = await self._icons_from_hash_caches(platform_ids)
        return await self.fill_missing_media(
            sources,
            db_rom_handler.set_ra_image_icons,
            db_rom_handler.set_ra_game_art,
            cached,
        )

    async def fill_missing_media(
        self,
        sources: Sequence[Mapping[str, Any]],
        save_icons: Callable[[Mapping[int, str]], object],
        save_art: Callable[[Mapping[int, Mapping[str, str]]], object],
        cached: Mapping[int, str] | None = None,
    ) -> dict[int, str]:
        """Resolve ImageIcon and screen art with one lookup per game still missing either."""
        from handler.metadata.earned_achievements import (
            ra_art_paths,
            ra_image_icon_path,
            stored_ra_art,
        )

        icons: dict[int, str | None] = {}
        arts: dict[int, dict[str, str] | None] = {}
        for source in sources:
            ra_id = source.get("ra_id")
            if isinstance(ra_id, bool) or not isinstance(ra_id, int) or ra_id <= 0:
                continue
            raw_icon = source.get("image_icon")
            path = "" if raw_icon == "" else ra_image_icon_path(raw_icon)
            if not path and cached:
                path = ra_image_icon_path(cached.get(ra_id))
            if path:
                icons[ra_id] = path
            elif raw_icon == "" and not icons.get(ra_id):
                icons[ra_id] = ""
            else:
                icons.setdefault(ra_id, None)
            record = stored_ra_art(source)
            if record is not None:
                arts[ra_id] = record
            else:
                arts.setdefault(ra_id, None)

        known_icons = {
            ra_id: path for ra_id, path in icons.items() if path is not None
        }
        if known_icons:
            save_icons(known_icons)
        known_arts = {ra_id: art for ra_id, art in arts.items() if art is not None}
        if known_arts:
            save_art(known_arts)

        missing = [
            ra_id
            for ra_id in icons
            if icons[ra_id] is None or arts.get(ra_id) is None
        ]
        fetched_icons: dict[int, str] = {}
        fetched_arts: dict[int, dict[str, str]] = {}
        if missing and self.is_enabled():
            empty_art = {
                "image_title": "",
                "image_ingame": "",
                "image_box_art": "",
            }
            for ra_id in missing:
                try:
                    details = await self.ra_service.get_game(ra_id)
                except Exception:
                    log.warning(
                        "RetroAchievements media lookup failed for game %s", ra_id
                    )
                    continue
                if not isinstance(details, dict):
                    if icons[ra_id] is None:
                        fetched_icons[ra_id] = ""
                    if arts.get(ra_id) is None:
                        fetched_arts[ra_id] = empty_art
                    continue
                if icons[ra_id] is None:
                    fetched_icons[ra_id] = (
                        ra_image_icon_path(details.get("ImageIcon")) or ""
                    )
                if arts.get(ra_id) is None:
                    fetched_arts[ra_id] = ra_art_paths(details) or empty_art
            if fetched_icons:
                save_icons(fetched_icons)
            if fetched_arts:
                save_art(fetched_arts)
        elif missing:
            log.warning(
                "RetroAchievements media lookup skipped: API key is not configured"
            )

        resolved = dict(known_icons)
        resolved.update(fetched_icons)
        return {ra_id: path for ra_id, path in resolved.items() if path}

    async def fill_image_icons(
        self,
        sources: Sequence[Mapping[str, Any]],
        save: Callable[[Mapping[int, str]], object],
        cached: Mapping[int, str] | None = None,
    ) -> dict[int, str]:
        """Resolve ImageIcon paths and hand new ones to ``save``."""
        from handler.metadata.earned_achievements import ra_image_icon_path

        by_game: dict[int, str | None] = {}
        for source in sources:
            ra_id = source.get("ra_id")
            if isinstance(ra_id, bool) or not isinstance(ra_id, int) or ra_id <= 0:
                continue
            path = ra_image_icon_path(source.get("image_icon"))
            if path is None and cached:
                path = ra_image_icon_path(cached.get(ra_id))
            if path:
                by_game[ra_id] = path
            else:
                by_game.setdefault(ra_id, None)

        known = {ra_id: path for ra_id, path in by_game.items() if path}
        if known:
            save(known)

        missing = [ra_id for ra_id, path in by_game.items() if not path]
        fetched: dict[int, str] = {}
        if missing and self.is_enabled():
            for ra_id in missing:
                path = await self._image_icon_from_api(ra_id)
                if path:
                    fetched[ra_id] = path
            if fetched:
                save(fetched)
        elif missing:
            log.warning(
                "RetroAchievements icon lookup skipped: API key is not configured"
            )
        return {**known, **fetched}

    async def _image_icon_from_api(self, ra_id: int) -> str | None:
        from handler.metadata.earned_achievements import ra_image_icon_path

        try:
            details = await self.ra_service.get_game(ra_id)
        except Exception:
            log.warning("RetroAchievements icon lookup failed for game %s", ra_id)
            return None
        if not isinstance(details, dict):
            return None
        return ra_image_icon_path(details.get("ImageIcon"))

    async def persist_missing_game_art(self) -> dict[int, dict[str, str]]:
        """Save each library game's title, in-game and box art once."""
        from handler.database import db_rom_handler

        sources = db_rom_handler.get_library_achievement_sources()
        return await self.fill_game_art(sources, db_rom_handler.set_ra_game_art)

    async def fill_game_art(
        self,
        sources: Sequence[Mapping[str, Any]],
        save: Callable[[Mapping[int, Mapping[str, str]]], object],
    ) -> dict[int, dict[str, str]]:
        """Resolve title, in-game and box art. The filename comes from the reply, not the game id."""
        from handler.metadata.earned_achievements import stored_ra_art

        by_game: dict[int, dict[str, str] | None] = {}
        incomplete: set[int] = set()
        for source in sources:
            ra_id = source.get("ra_id")
            if isinstance(ra_id, bool) or not isinstance(ra_id, int) or ra_id <= 0:
                continue
            record = stored_ra_art(source)
            if record is not None:
                by_game[ra_id] = record
            else:
                incomplete.add(ra_id)
                by_game.setdefault(ra_id, None)

        known = {ra_id: art for ra_id, art in by_game.items() if art is not None}
        pending_copy = {
            ra_id: known[ra_id] for ra_id in incomplete if ra_id in known
        }
        if pending_copy:
            save(pending_copy)

        missing = [ra_id for ra_id, art in by_game.items() if art is None]
        fetched: dict[int, dict[str, str]] = {}
        if missing and self.is_enabled():
            for ra_id in missing:
                art = await self._game_art_from_api(ra_id)
                if art is not None:
                    fetched[ra_id] = art
            if fetched:
                save(fetched)
        elif missing:
            log.warning(
                "RetroAchievements art lookup skipped: API key is not configured"
            )
        return {**known, **fetched}

    async def _game_art_from_api(self, ra_id: int) -> dict[str, str] | None:
        from handler.metadata.earned_achievements import ra_art_paths

        try:
            details = await self.ra_service.get_game(ra_id)
        except Exception:
            log.warning("RetroAchievements art lookup failed for game %s", ra_id)
            return None
        # An unknown id comes back empty. Record that so the page does not ask again.
        if not isinstance(details, dict):
            return {"image_title": "", "image_ingame": "", "image_box_art": ""}
        return ra_art_paths(details)

    async def _icons_from_hash_caches(
        self, platform_ids: Sequence[int]
    ) -> dict[int, str]:
        """ImageIcon paths already stored inside a platform hash cache."""
        from handler.metadata.earned_achievements import ra_image_icon_path

        found: dict[int, str] = {}
        seen: set[int] = set()
        for platform_id in platform_ids:
            if platform_id in seen:
                continue
            seen.add(platform_id)
            if not await self._exists_cache_file(platform_id):
                continue
            file_path = self._get_hashes_file_path(platform_id)
            try:
                raw = await fs_resource_handler.read_file(file_path)
                payload = json.loads(raw.decode("utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                log.warning(
                    "Couldn't read the RetroAchievements hash cache for platform %s: %s",
                    platform_id,
                    type(exc).__name__,
                )
                continue
            if not isinstance(payload, dict):
                continue
            for value in payload.values():
                if not isinstance(value, dict):
                    continue
                game_id = value.get("ID")
                path = ra_image_icon_path(value.get("ImageIcon"))
                if (
                    path
                    and isinstance(game_id, int)
                    and not isinstance(game_id, bool)
                    and game_id > 0
                ):
                    found[game_id] = path
        return found


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
    UPS.MSX2: {"id": 29, "name": "MSX2"},
    UPS.MEGA_DUCK_SLASH_COUGAR_BOY: {
        "id": 69,
        "name": "Mega Duck/Cougar Boy",
    },
    UPS.NES: {"id": 7, "name": "NES"},
    UPS.FAMICOM: {"id": 7, "name": "Family Computer"},
    UPS.FDS: {"id": 81, "name": "Famicom Disk System"},
    UPS.NEO_GEO_CD: {"id": 56, "name": "Neo Geo CD"},
    UPS.NEOGEOAES: {"id": 27, "name": "Neo Geo AES"},
    UPS.NEOGEOMVS: {"id": 27, "name": "Neo Geo MVS"},
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
    UPS.SUPERGRAFX: {"id": 8, "name": "SuperGrafx"},
    UPS.UZEBOX: {"id": 80, "name": "Uzebox"},
    UPS.VECTREX: {"id": 46, "name": "Vectrex"},
    UPS.VIRTUALBOY: {"id": 28, "name": "Virtual Boy"},
    UPS.WASM_4: {"id": 72, "name": "WASM-4"},
    UPS.SUPERVISION: {
        "id": 63,
        "name": "Watara/QuickShot Supervision",
    },
    UPS.WIN: {"id": 102, "name": "Windows"},
    UPS.WII: {"id": 19, "name": "Wii"},
    UPS.WONDERSWAN: {"id": 53, "name": "WonderSwan"},
    UPS.WONDERSWAN_COLOR: {"id": 53, "name": "WonderSwan Color"},
}
# RetroAchievements hashes only MAME and FinalBurn sets, by filename.
RA_PLATFORM_LIST |= arcade_fallbacks(RA_PLATFORM_LIST, ARCADE_SET_PLATFORMS)

fill_duplicate_slugs(RA_PLATFORM_LIST)
