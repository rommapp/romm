"""Maps RetroArch Cloud Sync's ``<root>/<core>/<file>`` namespace onto RomM's
per-ROM asset storage, and back again for the ``manifest.server`` it diffs."""

from __future__ import annotations

import os
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

from handler import cloud_sync_psp
from handler.cloud_sync_emulator_names import to_retroarch_dir_name, to_romm_emulator
from handler.database import (
    db_rom_handler,
    db_save_handler,
    db_screenshot_handler,
    db_state_handler,
)
from handler.filesystem import fs_asset_handler, fs_cloud_sync_blob_handler
from handler.redis_handler import async_cache
from models.assets import Save, Screenshot, State
from models.rom import Rom
from models.user import User

AssetKind = Literal["saves", "states"]

MANIFEST_FILE_NAME = "manifest.server"

ASSET_ROOTS: tuple[AssetKind, ...] = ("saves", "states")

# RetroArch's config/thumbnails/system sync categories belong to no ROM, so
# they're kept as opaque per-user blobs.
BLOB_CATEGORIES = ("config", "thumbnails", "system")

# `<game>.state`, `<game>.state3`, `<game>.state.auto`: the auto suffix makes
# this a two-segment extension, which splitext alone gets wrong.
STATE_SUFFIX_PATTERN = re.compile(r"\.state\d*(?:\.auto)?$", re.IGNORECASE)

# Rehashing every asset on each manifest fetch would read gigabytes. Keys carry
# size and mtime, so a changed file misses the cache instead of going stale.
_HASH_CACHE_TTL_SECONDS = 60 * 60 * 24


@dataclass(frozen=True)
class CloudSyncPath:
    """A parsed client-side path, e.g. ``saves/Snes9x/Super Mario World.srm``."""

    kind: AssetKind
    emulator: str | None
    file_name: str

    @property
    def is_state_screenshot(self) -> bool:
        return self.kind == "states" and is_state_screenshot_path(self.file_name)


def split_segments(path: str) -> list[str] | None:
    """A client path's non-empty segments, or None if any is `.` or `..`."""
    segments = [segment for segment in path.strip("/").split("/") if segment]
    if any(segment in (os.curdir, os.pardir) for segment in segments):
        return None
    return segments


def parse_cloud_sync_path(path: str) -> CloudSyncPath | None:
    """Parse a ``<root>/[<core>/]<file>`` client path, or None if unsupported."""
    segments = split_segments(path)
    if segments is None or not 2 <= len(segments) <= 3:
        return None

    if segments[0] not in ASSET_ROOTS:
        return None
    kind = cast(AssetKind, segments[0])

    # RomM's web player matches saves on the lowercase libretro core id, not
    # RetroArch's display-cased folder name.
    return CloudSyncPath(
        kind=kind,
        emulator=to_romm_emulator(segments[1]) if len(segments) == 3 else None,
        file_name=segments[-1],
    )


def is_state_screenshot_path(file_name: str) -> bool:
    """Whether a `states/...` file is the `<state file name>.png` RetroArch syncs."""
    return file_name.lower().endswith(".png")


def game_name_from_file_name(kind: AssetKind, file_name: str) -> str:
    """The ROM file name (minus extension) an asset file belongs to."""
    if kind == "states":
        base = (
            file_name[: -len(".png")]
            if is_state_screenshot_path(file_name)
            else file_name
        )
        stripped = STATE_SUFFIX_PATTERN.sub("", base)
        if stripped != base:
            return stripped
        return os.path.splitext(base)[0]

    return os.path.splitext(file_name)[0]


def state_slot_suffix(file_name: str) -> str:
    """The slot suffix (``state``, ``state1``, ``state.auto``) a state name ends in.

    States have no ``slot`` column, so this groups them into RetroArch's load
    slots. A web-player state (``<rom> [<timestamp>].state``) lands in slot 0.
    """
    match = STATE_SUFFIX_PATTERN.search(file_name)
    if match:
        return match.group(0)[1:].lower()
    return os.path.splitext(file_name)[1][1:].lower()


def recency_key(asset: Save | State) -> tuple[datetime, int]:
    """Recency order, with `id` breaking ties on a shared timestamp."""
    return (asset.updated_at, asset.id)


def group_states_by_slot(
    states: Iterable[State],
) -> dict[tuple[int, str | None, str], State]:
    """The newest state in each (rom, emulator, slot) bucket."""
    latest: dict[tuple[int, str | None, str], State] = {}
    for state in states:
        key = (state.rom_id, state.emulator, state_slot_suffix(state.file_name))
        current = latest.get(key)
        if current is None or recency_key(state) > recency_key(current):
            latest[key] = state

    return latest


def canonical_state_file_name(rom: Rom, slot_suffix: str) -> str:
    """The name RetroArch gives this slot, which the manifest advertises."""
    return f"{rom.fs_name_no_ext}.{slot_suffix}"


def resolve_state_by_slot(
    user: User, rom: Rom, emulator: str | None, requested_file_name: str
) -> State | None:
    """The newest state in the slot a canonical name points at, whatever its name."""
    states = db_state_handler.get_states(user_id=user.id, rom_ids=[rom.id])
    key = (rom.id, emulator, state_slot_suffix(requested_file_name))
    return group_states_by_slot(states).get(key)


def state_screenshot(state: State) -> Screenshot | None:
    """The screenshot synced alongside this exact state.

    `State.screenshot` also matches on the name stem, which a RetroArch slot
    name (`<rom>.state1`) shares with every other slot's and gallery shot.
    """
    exact_name = f"{state.file_name}.png"
    screenshot = db_screenshot_handler.get_screenshot(
        rom_id=state.rom_id, user_id=state.user_id, file_name=exact_name
    )
    if screenshot and screenshot.file_name == exact_name:
        return screenshot

    if state.file_name_no_ext == state.rom.fs_name_no_ext:
        return None

    screenshot = state.screenshot
    return None if screenshot is None or screenshot.is_gallery else screenshot


def resolve_state_screenshot_by_slot(
    user: User, rom: Rom, emulator: str | None, requested_file_name: str
) -> Screenshot | None:
    """The screenshot of the state a ``<slot>.png`` name resolves to."""
    state = resolve_state_by_slot(
        user, rom, emulator, requested_file_name[: -len(".png")]
    )
    return state_screenshot(state) if state else None


def build_cloud_sync_path(kind: AssetKind, emulator: str | None, file_name: str) -> str:
    if emulator:
        return f"{kind}/{to_retroarch_dir_name(emulator)}/{file_name}"
    return f"{kind}/{file_name}"


def build_asset_file_path(
    user: User, rom: Rom, kind: AssetKind, emulator: str | None
) -> str:
    build_path = (
        fs_asset_handler.build_saves_file_path
        if kind == "saves"
        else fs_asset_handler.build_states_file_path
    )
    return build_path(
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=emulator,
    )


def parse_cloud_sync_blob_path(path: str) -> str | None:
    """A blob-category client path as ``category/...``, or None if it isn't one.

    Nesting is arbitrary: RetroArch mirrors its on-device tree here.
    """
    segments = split_segments(path)
    if segments is None or len(segments) < 2:
        return None

    if segments[0] not in BLOB_CATEGORIES:
        return None

    return "/".join(segments)


def user_blob_path(user: User, blob_path: str) -> str:
    """Where a parsed blob path lives on disk, namespaced by user."""
    return f"{fs_asset_handler.user_folder_path(user)}/{blob_path}"


async def _cached_md5(
    cache_key: str, compute: Callable[[], Awaitable[str | None]]
) -> str | None:
    cached = await async_cache.get(cache_key)
    if cached:
        return str(cached)

    digest = await compute()
    if digest:
        await async_cache.set(cache_key, digest, ex=_HASH_CACHE_TTL_SECONDS)

    return digest


async def blob_md5(user: User, blob_path: str) -> str | None:
    disk_path = user_blob_path(user, blob_path)
    try:
        stat = fs_cloud_sync_blob_handler.validate_path(disk_path).stat()
    except (ValueError, OSError):
        return None

    return await _cached_md5(
        f"romm:cloud_sync:blob_md5:{user.id}:{blob_path}:{stat.st_size}:{stat.st_mtime}",
        lambda: fs_cloud_sync_blob_handler.compute_file_md5(disk_path),
    )


async def build_blob_manifest_entries(user: User) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for category in BLOB_CATEGORIES:
        prefix = f"{fs_asset_handler.user_folder_path(user)}/{category}"
        for relative in await fs_cloud_sync_blob_handler.list_blob_paths(prefix):
            blob_path = f"{category}/{relative}"
            digest = await blob_md5(user, blob_path)
            if not digest:
                continue
            entries.append({"path": blob_path, "hash": digest})

    return entries


def resolve_roms(
    game_names: Iterable[str], can_see: Callable[[Rom], bool]
) -> dict[str, Rom]:
    """The ROM each cloud-sync game name belongs to, matched on file name alone.

    An ambiguous name resolves to its first visible ROM by id, so it stays
    stable across syncs.
    """
    names = set(game_names)
    exact: dict[str, Rom] = {}
    # MariaDB's default collation matches case-insensitively; PostgreSQL doesn't.
    folded: dict[str, Rom] = {}
    for rom in db_rom_handler.get_roms_by_fs_names_no_ext(names):
        if can_see(rom):
            exact.setdefault(rom.fs_name_no_ext, rom)
            folded.setdefault(rom.fs_name_no_ext.casefold(), rom)

    resolved = {name: exact.get(name) or folded.get(name.casefold()) for name in names}
    return {name: rom for name, rom in resolved.items() if rom}


def resolve_rom(game_name: str, can_see: Callable[[Rom], bool]) -> Rom | None:
    return resolve_roms([game_name], can_see).get(game_name)


async def asset_md5(asset: Save | State | Screenshot) -> str | None:
    return await _cached_md5(
        f"romm:cloud_sync:md5:{asset.full_path}"
        f":{asset.file_size_bytes}:{asset.updated_at.timestamp()}",
        lambda: fs_asset_handler.compute_file_md5(asset.full_path),
    )


async def build_manifest(
    user: User, can_see: Callable[[Rom], bool]
) -> list[dict[str, str]]:
    """The server manifest RetroArch diffs against, sorted by path.

    Slotted saves are RomM's own timestamped history, which no core would load,
    so they're left out. Each state slot lists its newest state under
    RetroArch's canonical name.
    """
    saves = db_save_handler.get_saves(user_id=user.id, slot_is_null=True)
    listed_saves = [
        save
        for save in saves
        if not save.missing_from_fs
        and can_see(save.rom)
        and not cloud_sync_psp.is_psp_bundle_file_name(save.file_name)
    ]
    listed_states = [
        (emulator, canonical_state_file_name(state.rom, slot_suffix), state)
        for (_rom_id, emulator, slot_suffix), state in group_states_by_slot(
            db_state_handler.get_states(user_id=user.id)
        ).items()
        if not state.missing_from_fs and can_see(state.rom)
    ]

    # A path carries no platform, so only the ROM that GET/PUT/DELETE would
    # resolve it to may claim it; a same-named ROM elsewhere would shadow it.
    owners = resolve_roms(
        [game_name_from_file_name("saves", save.file_name) for save in listed_saves]
        + [game_name_from_file_name("states", name) for _, name, _ in listed_states],
        can_see,
    )

    def is_addressable(rom: Rom, kind: AssetKind, file_name: str) -> bool:
        owner = owners.get(game_name_from_file_name(kind, file_name))
        return owner is not None and owner.id == rom.id

    entries: list[dict[str, str]] = []

    async def add(path: str, asset: Save | State | Screenshot) -> bool:
        digest = await asset_md5(asset)
        if digest:
            entries.append({"path": path, "hash": digest})
        return bool(digest)

    for save in listed_saves:
        if is_addressable(save.rom, "saves", save.file_name):
            await add(
                build_cloud_sync_path("saves", save.emulator, save.file_name), save
            )

    for emulator, file_name, state in listed_states:
        if not is_addressable(state.rom, "states", file_name):
            continue

        state_path = build_cloud_sync_path("states", emulator, file_name)
        if not await add(state_path, state):
            continue

        screenshot = state_screenshot(state)
        if screenshot and not screenshot.missing_from_fs:
            await add(f"{state_path}.png", screenshot)

    entries += await build_blob_manifest_entries(user)
    entries += await cloud_sync_psp.build_psp_manifest_entries(saves, can_see)

    entries.sort(key=lambda entry: entry["path"])
    return entries
