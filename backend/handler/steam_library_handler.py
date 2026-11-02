"""Linking a user's Steam account and importing the games it owns."""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final

from adapters.services.steam import SteamWebAPIError, SteamWebApiService
from adapters.services.steam_types import SteamOwnedGame, SteamPlayerSummary
from config import STEAM_API_KEY
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from handler.database import (
    db_collection_handler,
    db_platform_handler,
    db_steam_library_handler,
    db_user_handler,
)
from handler.filesystem import fs_platform_handler
from handler.metadata.steam_handler import STEAM_PLATFORMS
from handler.scan_handler import build_physical_fs_path, scan_platform
from logger.logger import log
from models.platform import Platform
from models.rom import Rom, RomStorefront
from models.steam_library import SteamLibraryEntry
from models.user import User
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


def _refresh_ownership_collections(user_id: int, app_ids: Sequence[int]) -> None:
    """Follow a change in what a user owns into their smart collections filtering on it."""
    try:
        db_collection_handler.refresh_smart_collections_for_roms(
            db_steam_library_handler.get_rom_ids_by_app_ids(app_ids),
            membership_only=True,
            user_id=user_id,
            criterion="owned_on_steam",
        )
    except Exception as e:
        # The ownership change is committed, so a stale count is the worst this costs.
        log.error(f"Couldn't refresh smart collections for Steam apps {app_ids}: {e}")


def _forget_library(user_id: int) -> None:
    _refresh_ownership_collections(
        user_id, db_steam_library_handler.delete_entries(user_id)
    )


def link_steam_profile(user: User, summary: SteamPlayerSummary) -> User:
    """Link the Steam account `summary` describes, forgetting another one's games."""
    previous = user.steam_id
    # The account changes first, so a sync of the previous one discards its result.
    linked = db_user_handler.update_user(
        user.id,
        {"steam_id": summary["steamid"], "steam_persona_name": summary["personaname"]},
    )
    if previous and previous != summary["steamid"]:
        _forget_library(user.id)
    return linked


def unlink_steam_profile(user: User) -> User:
    """Unlink a user's Steam account and forget which games it owns."""
    unlinked = db_user_handler.update_user(
        user.id, {"steam_id": None, "steam_persona_name": None}
    )
    _forget_library(user.id)
    return unlinked


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
        fs_path=build_physical_fs_path(platform, subdir=STEAM_FS_SUBDIR),
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
    timestamp = game.get("rtime_last_played")
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

    store_only = db_steam_library_handler.add_store_only_roms(
        [
            _store_only_rom(platform, game)
            for game in games
            if game["appid"] not in rom_ids
        ]
    )
    rom_ids.update(store_only.rom_ids)
    result.created = store_only.created

    entries = [
        SteamLibraryEntry(
            rom_id=rom_ids[game["appid"]],
            steam_app_id=game["appid"],
            playtime_minutes=game.get("playtime_forever", 0),
            last_played_at=_last_played(game),
        )
        for game in games
        if game["appid"] in rom_ids
    ]

    changes = db_steam_library_handler.replace_entries(user.id, steam_id, entries)
    if changes is None:
        raise SteamLibraryError(
            f"{user.username}'s Steam account changed during the sync"
        )
    result.removed = len(changes.removed)
    _refresh_ownership_collections(user.id, [*changes.added, *changes.removed])
    result.unmatched_rom_ids = (
        db_steam_library_handler.get_unmatched_store_only_rom_ids(
            [entry.rom_id for entry in entries]
        )
    )
    return result
