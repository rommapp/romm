"""RetroArch Cloud Sync support.

RetroArch's cloud-sync driver speaks a narrow slice of WebDAV: it GETs a JSON
manifest of ``{path, hash}`` entries from ``manifest.server``, diffs it against
its local state, then GETs/PUTs/DELETEs individual files. It never issues
PROPFIND, so no collection listing is involved.

This module maps that flat ``<root>/<core>/<file>`` namespace onto RomM's
per-ROM asset storage, and back again for the manifest.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from handler.database import db_rom_handler, db_save_handler, db_state_handler
from handler.filesystem import fs_asset_handler
from handler.redis_handler import async_cache
from models.assets import Save, State
from models.rom import Rom
from models.user import User

AssetKind = Literal["saves", "states"]

MANIFEST_FILE_NAME = "manifest.server"

ASSET_ROOTS: dict[str, AssetKind] = {"saves": "saves", "states": "states"}

# `<game>.state`, `<game>.state3`, `<game>.state.auto` — the auto suffix makes
# this a two-segment extension, which splitext alone gets wrong.
STATE_SUFFIX_PATTERN = re.compile(r"\.state\d*(?:\.auto)?$", re.IGNORECASE)

# A sync fetches the whole manifest at once, and rehashing every state file on
# each one would read gigabytes. Entries are keyed by size and mtime, so a
# changed file misses the cache rather than serving a stale digest.
_HASH_CACHE_TTL_SECONDS = 60 * 60 * 24


@dataclass(frozen=True)
class CloudSyncPath:
    """A parsed client-side path, e.g. ``saves/Snes9x/Super Mario World.srm``."""

    kind: AssetKind
    emulator: str | None
    file_name: str


def parse_cloud_sync_path(path: str) -> CloudSyncPath | None:
    """Parse a client path, or None when it is not a supported asset path.

    Accepts ``<root>/<file>`` and ``<root>/<core>/<file>``; RetroArch produces
    the latter when "sort saves into folders by core name" is on.
    """
    segments = [segment for segment in path.strip("/").split("/") if segment]
    if not 2 <= len(segments) <= 3:
        return None

    if any(segment in (os.curdir, os.pardir) for segment in segments):
        return None

    kind = ASSET_ROOTS.get(segments[0])
    if kind is None:
        return None

    return CloudSyncPath(
        kind=kind,
        emulator=segments[1] if len(segments) == 3 else None,
        file_name=segments[-1],
    )


def game_name_from_file_name(kind: AssetKind, file_name: str) -> str:
    """The ROM file name (minus extension) an asset file belongs to."""
    if kind == "states":
        stripped = STATE_SUFFIX_PATTERN.sub("", file_name)
        if stripped != file_name:
            return stripped

    return os.path.splitext(file_name)[0]


def build_cloud_sync_path(kind: AssetKind, emulator: str | None, file_name: str) -> str:
    if emulator:
        return f"{kind}/{emulator}/{file_name}"
    return f"{kind}/{file_name}"


def build_asset_file_path(
    user: User, rom: Rom, kind: AssetKind, emulator: str | None
) -> str:
    if kind == "saves":
        return fs_asset_handler.build_saves_file_path(
            user=user,
            platform_fs_slug=rom.platform.fs_slug,
            rom_id=rom.id,
            emulator=emulator,
        )

    return fs_asset_handler.build_states_file_path(
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )


def resolve_rom(game_name: str, can_see: Callable[[Rom], bool]) -> Rom | None:
    """The ROM a cloud-sync file belongs to, matched on file name alone.

    When several platforms hold a ROM of the same name the match is ambiguous;
    the first candidate wins so it stays stable across syncs.
    """
    for rom in db_rom_handler.get_roms_by_fs_name_no_ext(game_name):
        if can_see(rom):
            return rom

    return None


async def asset_md5(asset: Save | State) -> str | None:
    cache_key = (
        f"romm:cloud_sync:md5:{asset.full_path}"
        f":{asset.file_size_bytes}:{asset.updated_at.timestamp()}"
    )

    cached = await async_cache.get(cache_key)
    if cached:
        return cached.decode() if isinstance(cached, bytes) else str(cached)

    digest = await fs_asset_handler.compute_file_md5(asset.full_path)
    if digest:
        await async_cache.set(cache_key, digest, ex=_HASH_CACHE_TTL_SECONDS)

    return digest


async def build_manifest(
    user: User, can_see: Callable[[Rom], bool]
) -> list[dict[str, str]]:
    """The server manifest RetroArch diffs against, sorted by path.

    Slotted saves are RomM's own versioned history: every revision carries a
    datetime tag in its file name, so surfacing them would hand RetroArch a
    growing pile of files no core would ever load.
    """
    assets: list[tuple[AssetKind, Save | State]] = [
        ("saves", save)
        for save in db_save_handler.get_saves(user_id=user.id)
        if save.slot is None
    ]
    assets += [
        ("states", state) for state in db_state_handler.get_states(user_id=user.id)
    ]

    entries: list[dict[str, str]] = []
    for kind, asset in assets:
        if asset.missing_from_fs or not can_see(asset.rom):
            continue

        digest = await asset_md5(asset)
        if not digest:
            continue

        entries.append(
            {
                "path": build_cloud_sync_path(kind, asset.emulator, asset.file_name),
                "hash": digest,
            }
        )

    entries.sort(key=lambda entry: entry["path"])
    return entries
