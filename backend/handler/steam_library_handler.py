"""Linking a user's Steam account and importing the games it owns."""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final, TypedDict, cast

from rq.exceptions import DuplicateJobError
from sqlalchemy.exc import IntegrityError

from adapters.services.steam import SteamWebAPIError, SteamWebApiService
from adapters.services.steam_types import (
    SteamOwnedGame,
    SteamPlayerAchievement,
    SteamPlayerSummary,
)
from config import STEAM_API_KEY
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from handler.database import (
    db_collection_handler,
    db_platform_handler,
    db_rom_handler,
    db_steam_library_handler,
    db_user_handler,
)
from handler.filesystem import fs_platform_handler, fs_rom_handler
from handler.metadata.steam_handler import STEAM_PLATFORMS
from handler.redis_handler import low_prio_queue
from handler.scan_handler import scan_platform
from logger.logger import log
from models.platform import Platform
from models.rom import Rom, RomStorefront, RomUserStatus
from models.steam_library import SteamLibraryEntry
from models.user import User
from tasks.registry import SYNC_STEAM_LIBRARIES_SPEC
from utils import int_or_none
from utils.filesystem import sanitize_filename
from utils.platform_slugs import UniversalPlatformSlug as UPS

# Store-only games sit in a folder no scan lists, like physical games do.
STEAM_FS_SUBDIR: Final = ".steam"
STEAM_LIBRARY_PLATFORM: Final = UPS.WIN

STEAM_ID64_RE: Final = re.compile(r"^7656119\d{10}$")
STEAM_VANITY_RE: Final = re.compile(r"^[A-Za-z0-9_-]{2,32}$")
STEAM_PROFILE_URL_RE: Final = re.compile(
    r"^(?:https?://)?(?:www\.)?steamcommunity\.com/(profiles|id)/([^/?#]+)/?(?:[?#].*)?$",
    re.IGNORECASE,
)


class SteamLibraryError(Exception):
    """A Steam account can't be linked or synced, worded for the user."""


@dataclass
class SteamSyncResult:
    owned: int = 0
    linked: int = 0
    created: int = 0
    removed: int = 0
    # Store-only roms no metadata source matched yet, new ones included.
    unmatched_rom_ids: list[int] = field(default_factory=list)


# Reads per achievements job, so a large first read stays within the job's
# timeout and the rest are read after the next library sync.
STEAM_ACHIEVEMENT_READS_PER_SYNC: Final[int] = 100
# Failed reads in a row that mean Steam itself is struggling.
STEAM_ACHIEVEMENT_FAILURES_IN_A_ROW: Final[int] = 3
# A failed job keeps its fixed id this long, which must not block the next one.
STEAM_ACHIEVEMENTS_SYNC_FAILURE_TTL_SECONDS: Final[int] = 300


class SteamEarnedAchievement(TypedDict):
    api_name: str
    # Epoch seconds.
    unlock_time: int


class SteamUserGameProgression(TypedDict):
    rom_steam_id: int
    # The game's last-played time and playtime when its unlocks were read, to
    # skip it until it is played again.
    rtime_last_played: int | None
    playtime_forever: int
    num_achievements: int
    num_unlocked: int
    earned_achievements: list[SteamEarnedAchievement]


class SteamUserProgression(TypedDict):
    total: int
    results: list[SteamUserGameProgression]


def is_steam_game_completed(progression: SteamUserGameProgression) -> bool:
    """Whether every achievement of the game is unlocked."""
    return 0 < progression["num_achievements"] == progression["num_unlocked"]


def steam_web_api() -> SteamWebApiService:
    if not STEAM_API_KEY:
        raise SteamLibraryError("Set STEAM_API_KEY to import Steam libraries")
    return SteamWebApiService()


def parse_steam_profile(profile: str) -> tuple[str | None, str | None]:
    """Split what a user typed into a SteamID64 or a custom URL name.

    Returns:
        `(steam_id, None)` or `(None, vanity_name)`.

    Raises:
        SteamLibraryError: The text is neither.
    """
    text = profile.strip()
    url = STEAM_PROFILE_URL_RE.match(text)
    if url:
        kind, value = url.group(1).lower(), url.group(2)
        if kind == "profiles" and STEAM_ID64_RE.match(value):
            return value, None
        if kind == "id" and STEAM_VANITY_RE.match(value):
            return None, value
    elif STEAM_ID64_RE.match(text):
        return text, None
    elif STEAM_VANITY_RE.match(text):
        return None, text

    raise SteamLibraryError(
        f"{text!r} isn't a SteamID64, a Steam profile link or a custom URL name"
    )


async def resolve_steam_profile(profile: str) -> SteamPlayerSummary:
    """Find the Steam account a SteamID64, profile link or custom URL name names."""
    steam_id, vanity_name = parse_steam_profile(profile)
    api = steam_web_api()
    try:
        if vanity_name is not None:
            steam_id = await api.resolve_vanity_url(vanity_name)
        if steam_id is None:
            raise SteamLibraryError(
                f"No Steam profile uses the custom URL {vanity_name!r}"
            )
        summary = await api.get_player_summary(steam_id)
    except SteamWebAPIError as exc:
        raise SteamLibraryError(str(exc)) from exc

    if summary is None:
        raise SteamLibraryError(f"No Steam account has the ID {steam_id}")
    return summary


def _refresh_ownership_collections(app_ids: Sequence[int]) -> None:
    """Follow a change in what a user owns into the smart collections filtering on it."""
    try:
        db_collection_handler.refresh_smart_collections_for_roms(
            db_steam_library_handler.get_rom_ids_by_app_ids(app_ids),
            membership_only=True,
        )
    except Exception as e:
        # The ownership change is committed, so a stale count is the worst this costs.
        log.error(f"Couldn't refresh smart collections for Steam apps {app_ids}: {e}")


def _forget_library(user_id: int) -> None:
    _refresh_ownership_collections(db_steam_library_handler.delete_entries(user_id))


def link_steam_profile(user: User, summary: SteamPlayerSummary) -> None:
    """Link the Steam account `summary` describes, forgetting another one's games."""
    previous = user.steam_id
    # The account changes first, so a sync of the previous one discards its result.
    switched = previous != summary["steamid"]
    changes: dict[str, object] = {
        "steam_id": summary["steamid"],
        "steam_persona_name": summary["personaname"],
    }
    if switched:
        changes["steam_progression"] = {}
    db_user_handler.update_user(user.id, changes)
    if previous and switched:
        _forget_library(user.id)


def unlink_steam_profile(user: User) -> None:
    """Unlink a user's Steam account and forget which games it owns."""
    db_user_handler.update_user(
        user.id,
        {"steam_id": None, "steam_persona_name": None, "steam_progression": {}},
    )
    _forget_library(user.id)


async def steam_library_platform() -> Platform:
    """The platform store-only Steam games go on, creating its folder if needed."""
    platform = db_platform_handler.get_platform_by_slug(STEAM_LIBRARY_PLATFORM)
    if platform is not None:
        return platform

    fs_slug = STEAM_LIBRARY_PLATFORM.value
    try:
        await fs_platform_handler.add_platform(fs_slug=fs_slug)
    except PlatformAlreadyExistsException:
        pass
    except OSError as exc:
        raise SteamLibraryError(
            f"Could not create the {fs_slug!r} platform folder for Steam games"
        ) from exc

    return db_platform_handler.add_platform(await scan_platform(fs_slug, [fs_slug]))


def _store_only_rom(platform: Platform, game: SteamOwnedGame) -> Rom:
    app_id = game["appid"]
    name = game.get("name") or f"Steam app {app_id}"
    return Rom(
        platform_id=platform.id,
        # The tag lets the Steam provider match by id, as it does for files.
        fs_name=sanitize_filename(f"{name} (steam-{app_id})"),
        fs_path=(
            f"{fs_rom_handler.get_roms_fs_structure(platform.fs_slug)}"
            f"/{STEAM_FS_SUBDIR}"
        ),
        fs_size_bytes=0,
        name=name,
        steam_id=app_id,
        storefront=RomStorefront.STEAM,
        url_cover="",
        url_manual="",
        url_screenshots=[],
    )


def _last_played(game: SteamOwnedGame) -> datetime | None:
    # Steam sends 0 for a game never played.
    timestamp = game.get("rtime_last_played") or 0
    return datetime.fromtimestamp(timestamp, timezone.utc) if timestamp else None


async def sync_steam_library(user: User) -> SteamSyncResult:
    """Make the user's Steam library entries match what their account owns.

    Raises:
        SteamLibraryError: The account isn't linked, Steam can't list its games,
            or the account changed during the sync.
    """
    steam_id = user.steam_id
    if not steam_id:
        raise SteamLibraryError(f"{user.username} has no linked Steam account")

    try:
        games = await steam_web_api().get_owned_games(steam_id)
    except SteamWebAPIError as exc:
        raise SteamLibraryError(str(exc)) from exc
    if games is None:
        raise SteamLibraryError(
            "Steam keeps this account's games private. Set the profile's "
            "Game details to Public in Steam's privacy settings"
        )

    platform = await steam_library_platform()
    rom_ids = db_steam_library_handler.get_rom_ids_by_steam_app_id(
        [slug.value for slug in STEAM_PLATFORMS],
        [game["appid"] for game in games],
    )
    result = SteamSyncResult(owned=len(games), linked=len(rom_ids))

    entries: list[SteamLibraryEntry] = []
    for game in games:
        app_id = game["appid"]
        if app_id not in rom_ids:
            try:
                rom = db_rom_handler.add_rom(_store_only_rom(platform, game))
            except IntegrityError:
                log.warning(
                    f"Skipping Steam app {app_id}: another game already uses its name"
                )
                continue
            rom_ids[app_id] = rom.id
            result.created += 1

        entries.append(
            SteamLibraryEntry(
                rom_id=rom_ids[app_id],
                steam_app_id=app_id,
                playtime_minutes=game.get("playtime_forever", 0),
                last_played_at=_last_played(game),
            )
        )

    changes = db_steam_library_handler.replace_entries(user.id, steam_id, entries)
    if changes is None:
        raise SteamLibraryError(
            f"{user.username}'s Steam account changed during the sync"
        )
    result.removed = len(changes.removed)
    _refresh_ownership_collections([*changes.added, *changes.removed])
    result.unmatched_rom_ids = (
        db_steam_library_handler.get_unmatched_store_only_rom_ids(
            [entry.rom_id for entry in entries]
        )
    )
    queue_steam_achievements_sync(user.id)
    return result


def _last_played_epoch(entry: SteamLibraryEntry) -> int | None:
    return int(entry.last_played_at.timestamp()) if entry.last_played_at else None


def _game_progression(
    entry: SteamLibraryEntry, achievements: list[SteamPlayerAchievement]
) -> SteamUserGameProgression:
    # Steam's reply arrives even when it strays, and this must pass `UserSchema`.
    named = [
        a
        for a in achievements
        if isinstance(a, dict) and isinstance(a.get("apiname"), str) and a["apiname"]
    ]
    earned = [
        SteamEarnedAchievement(
            # Steam's own "unknown" unlock time is 0.
            api_name=a["apiname"],
            unlock_time=int_or_none(a.get("unlocktime")) or 0,
        )
        for a in named
        if a.get("achieved") == 1
    ]
    return SteamUserGameProgression(
        rom_steam_id=entry.steam_app_id,
        rtime_last_played=_last_played_epoch(entry),
        playtime_forever=entry.playtime_minutes,
        num_achievements=len(named),
        num_unlocked=len(earned),
        earned_achievements=earned,
    )


async def get_steam_progression(
    steam_id: str,
    entries: Sequence[SteamLibraryEntry],
    current: SteamUserProgression | None,
) -> SteamUserProgression:
    """Read the unlocks of the played games in `entries`, up to a budget per sync.

    A game not played since `current` was read keeps its entry without a
    request. Once the budget is spent, Steam fails several reads in a row, or
    the player's game details turn out private, the remaining games keep what
    `current` has and wait for the next sync.
    """
    known_results = current.get("results", []) if current else []
    current_by_app_id = {p["rom_steam_id"]: p for p in known_results}
    api = steam_web_api()
    results: list[SteamUserGameProgression] = []
    reads = failures_in_a_row = 0
    private = False
    for entry in entries:
        if not entry.playtime_minutes:
            continue

        result = current_by_app_id.get(entry.steam_app_id)
        unchanged = (
            result
            and result["rtime_last_played"] == _last_played_epoch(entry)
            and result["playtime_forever"] == entry.playtime_minutes
        )
        if not (
            unchanged
            or private
            or reads >= STEAM_ACHIEVEMENT_READS_PER_SYNC
            or failures_in_a_row >= STEAM_ACHIEVEMENT_FAILURES_IN_A_ROW
        ):
            reads += 1
            try:
                achievements = await api.get_player_achievements(
                    steam_id, entry.steam_app_id
                )
            except SteamWebAPIError as exc:
                failures_in_a_row += 1
                log.warning(
                    f"Couldn't read achievements for Steam app {entry.steam_app_id}: {exc}"
                )
            else:
                failures_in_a_row = 0
                if achievements is None:
                    private = True
                else:
                    result = _game_progression(entry, achievements)
        if result:
            results.append(result)

    return SteamUserProgression(total=len(results), results=results)


async def sync_steam_achievements(user: User) -> None:
    """Store the user's unlocks and mark each fully unlocked game as completed."""
    steam_id = user.steam_id
    if not steam_id:
        return

    current = cast(SteamUserProgression | None, user.steam_progression)
    progression = await get_steam_progression(
        steam_id, db_steam_library_handler.get_entries(user.id), current
    )
    if progression == current or not db_steam_library_handler.replace_progression(
        user.id, steam_id, progression
    ):
        return

    completed = [
        game["rom_steam_id"]
        for game in progression["results"]
        if is_steam_game_completed(game)
    ]
    statuses = dict.fromkeys(
        db_steam_library_handler.get_rom_ids_by_app_ids(completed),
        RomUserStatus.COMPLETED_100,
    )
    db_rom_handler.set_rom_user_statuses(user.id, statuses)


def queue_steam_achievements_sync(user_id: int) -> None:
    """Read the user's unlocks in a job of their own, at most one at a time."""
    try:
        low_prio_queue.enqueue(
            "tasks.scheduled.sync_steam_libraries.sync_steam_achievements_job",
            kwargs={"user_id": user_id},
            job_id=f"steam_achievements_sync_{user_id}",
            unique=True,
            job_timeout=SYNC_STEAM_LIBRARIES_SPEC.timeout,
            result_ttl=0,
            # Not 0: RQ reads a stored 0 back as unset, which means a year.
            failure_ttl=STEAM_ACHIEVEMENTS_SYNC_FAILURE_TTL_SECONDS,
            meta={"task_name": "Steam achievements sync"},
        )
    except DuplicateJobError:
        pass
    except Exception:  # noqa: BLE001 - the next library sync queues it again
        log.exception("Failed to queue a Steam achievements sync")
