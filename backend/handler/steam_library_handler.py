"""Linking a user's Steam account and importing the games it owns."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final

from sqlalchemy.exc import IntegrityError

from adapters.services.steam_types import SteamOwnedGame, SteamPlayerSummary
from adapters.services.steam_web_api import SteamWebAPIError, SteamWebAPIService
from config import STEAM_API_KEY
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from handler.database import (
    db_platform_handler,
    db_rom_handler,
    db_steam_library_handler,
)
from handler.filesystem import fs_platform_handler, fs_rom_handler
from handler.metadata.steam_handler import STEAM_PLATFORMS
from handler.scan_handler import scan_platform
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


def steam_web_api() -> SteamWebAPIService:
    if not STEAM_API_KEY:
        raise SteamLibraryError("Set STEAM_API_KEY to import Steam libraries")
    return SteamWebAPIService(STEAM_API_KEY)


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

    Owned games already in the library are linked to their rom; the rest get a
    store-only rom. Store-only roms still unmatched are listed for a metadata
    scan, since a library scan never reaches a game without a file.

    Raises:
        SteamLibraryError: The account isn't linked, or Steam can't list its games.
    """
    if not user.steam_id:
        raise SteamLibraryError(f"{user.username} has no linked Steam account")

    try:
        games = await steam_web_api().get_owned_games(user.steam_id)
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

    result.removed = db_steam_library_handler.replace_entries(user.id, entries)
    result.unmatched_rom_ids = (
        db_steam_library_handler.get_unmatched_store_only_rom_ids(
            [entry.rom_id for entry in entries]
        )
    )
    return result
