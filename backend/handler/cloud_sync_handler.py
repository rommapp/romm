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
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal

from handler.cloud_sync_emulator_names import to_retroarch_dir_name, to_romm_emulator
from handler.database import db_rom_handler, db_save_handler, db_state_handler
from handler.filesystem import fs_asset_handler, fs_cloud_sync_blob_handler
from handler.redis_handler import async_cache
from models.assets import Save, Screenshot, State
from models.rom import Rom
from models.user import User

AssetKind = Literal["saves", "states"]

MANIFEST_FILE_NAME = "manifest.server"

ASSET_ROOTS: dict[str, AssetKind] = {"saves": "saves", "states": "states"}

# RetroArch's other three Cloud Sync categories (Settings -> Saving -> Cloud
# Sync -> Sync Configuration/Thumbnails/System Files). Unlike saves/states,
# none of these belong to a ROM, so they're kept as opaque per-user blobs
# instead of going through the asset/ROM matching machinery below.
BLOB_CATEGORIES = ("config", "thumbnails", "system")

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
    the latter when "sort saves into folders by core name" is on. The core
    segment is RetroArch's own directory casing (e.g. "Snes9x"), normalized
    here to RomM's `emulator` convention (e.g. "snes9x") -- storing it
    unnormalized would make the save invisible to RomM's own web player,
    which matches saves against the lowercase libretro core id.
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
        emulator=to_romm_emulator(segments[1]) if len(segments) == 3 else None,
        file_name=segments[-1],
    )


def is_state_screenshot_path(file_name: str) -> bool:
    """Whether a `states/...` file is the PNG screenshot RetroArch captures
    and syncs alongside a state (`<state file name>.png`), rather than the
    state itself."""
    return file_name.lower().endswith(".png")


def game_name_from_file_name(kind: AssetKind, file_name: str) -> str:
    """The ROM file name (minus extension) an asset file belongs to."""
    if kind == "states":
        base = file_name[: -len(".png")] if is_state_screenshot_path(file_name) else file_name
        stripped = STATE_SUFFIX_PATTERN.sub("", base)
        if stripped != base:
            return stripped
        return os.path.splitext(base)[0]

    return os.path.splitext(file_name)[0]


def state_slot_suffix(file_name: str) -> str:
    """The RetroArch slot suffix (``state``, ``state1``, ..., ``state.auto``)
    a state's file name ends in -- RomM has no ``slot`` column for states
    (unlike saves), so this is the only way to group a rom's states into the
    numbered load slots (0-999) RetroArch's own Load State menu offers.

    A state uploaded through RomM's web player instead carries a display
    label and timestamp (e.g. ``<rom> [2026-07-24 12-04-52-733].state``);
    that still ends in a bare ``.state``, so it lands in slot 0 alongside
    (and competing on recency with) any RetroArch-native slot-0 state --
    mirroring the shim's `assetHistoryKey`/`splitAssetFileName`, which
    resolved the identical ambiguity for the same reason: without this, a
    web-uploaded state either has no reachable slot at all, or (naively
    keyed by its raw file name) its own permanent one-off slot that grows
    without bound.
    """
    match = STATE_SUFFIX_PATTERN.search(file_name)
    if match:
        return match.group(0)[1:].lower()
    return os.path.splitext(file_name)[1][1:].lower()


def latest_state_for_slot(
    states: Iterable[State], rom_id: int, emulator: str | None, slot_suffix: str
) -> State | None:
    """The state RetroArch would see for a given (rom, emulator, slot) --
    whichever matching row was updated most recently, regardless of whether
    it came from a real RetroArch upload or RomM's own web player. Ties
    (e.g. a bulk migration timestamp shared by several rows) break on `id`,
    the same deterministic tiebreaker the shim's `sortByRecency` uses, so a
    manifest build and a later GET/DELETE for the same slot always agree on
    which row "the newest" actually is.
    """
    candidates = [
        state
        for state in states
        if state.rom_id == rom_id
        and state.emulator == emulator
        and state_slot_suffix(state.file_name) == slot_suffix
    ]
    if not candidates:
        return None

    return max(candidates, key=lambda state: (state.updated_at, state.id))


def group_states_by_slot(
    states: Iterable[State],
) -> dict[tuple[int, str | None, str], State]:
    """Every (rom, emulator, slot) bucket collapsed to its newest state --
    the same grouping `latest_state_for_slot` performs, computed once for
    every state instead of once per slot so `build_manifest` doesn't rescan
    the full state list for every rom it lists."""
    latest: dict[tuple[int, str | None, str], State] = {}
    for state in states:
        key = (state.rom_id, state.emulator, state_slot_suffix(state.file_name))
        current = latest.get(key)
        if current is None or (state.updated_at, state.id) > (
            current.updated_at,
            current.id,
        ):
            latest[key] = state

    return latest


def canonical_state_file_name(rom: Rom, slot_suffix: str) -> str:
    """The file name RetroArch's own upload for this (rom, slot) would carry
    -- what the manifest advertises, and what a GET/DELETE for this slot
    must resolve back to the real underlying row via
    ``resolve_state_by_slot``, regardless of that row's actual file name."""
    return f"{rom.fs_name_no_ext}.{slot_suffix}"


def resolve_state_by_slot(
    user: User, rom: Rom, emulator: str | None, requested_file_name: str
) -> State | None:
    """The state a GET/DELETE for `requested_file_name` resolves to -- the
    same "newest row in this (rom, emulator, slot) bucket" `build_manifest`
    already advertised, found by re-deriving the slot from the *requested*
    canonical name rather than trusting any single row's own file name to
    match it exactly (it usually won't, for a web-player-created state)."""
    slot_suffix = state_slot_suffix(requested_file_name)
    states = db_state_handler.get_states(user_id=user.id, rom_id=rom.id)
    return latest_state_for_slot(states, rom.id, emulator, slot_suffix)


def resolve_state_screenshot_by_slot(
    user: User, rom: Rom, emulator: str | None, requested_file_name: str
) -> Screenshot | None:
    """The screenshot a GET/DELETE for `<slot>.png` resolves to -- whatever
    is attached to the same state ``resolve_state_by_slot`` would return for
    that slot, since RetroArch always syncs a state's screenshot under
    ``<state file name>.png``."""
    if not is_state_screenshot_path(requested_file_name):
        return None

    state = resolve_state_by_slot(
        user, rom, emulator, requested_file_name[: -len(".png")]
    )
    return state.screenshot if state else None


def build_cloud_sync_path(kind: AssetKind, emulator: str | None, file_name: str) -> str:
    if emulator:
        return f"{kind}/{to_retroarch_dir_name(emulator)}/{file_name}"
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


def parse_cloud_sync_blob_path(path: str) -> str | None:
    """A client path under one of the opaque blob categories, normalized to
    a plain ``category/...`` posix string, or None if it isn't one.

    Unlike asset paths these keep arbitrary nesting: RetroArch mirrors its
    own on-device directory tree here (e.g. thumbnail packs are organized as
    ``thumbnails/<system>/Named_Boxarts/<game>.png``), so there's no fixed
    segment count to enforce.
    """
    segments = [segment for segment in path.strip("/").split("/") if segment]
    if len(segments) < 2:
        return None

    if any(segment in (os.curdir, os.pardir) for segment in segments):
        return None

    if segments[0] not in BLOB_CATEGORIES:
        return None

    return "/".join(segments)


def user_blob_path(user: User, blob_path: str) -> str:
    """Where a parsed blob path lives on disk, namespaced by user so two
    RetroArch installs syncing to the same RomM instance under different
    accounts never see each other's config/thumbnails/system files."""
    return f"{fs_asset_handler.user_folder_path(user)}/{blob_path}"


async def blob_md5(user: User, blob_path: str) -> str | None:
    try:
        resolved = fs_cloud_sync_blob_handler.validate_path(
            user_blob_path(user, blob_path)
        )
        stat = resolved.stat()
    except (ValueError, OSError):
        return None

    cache_key = (
        f"romm:cloud_sync:blob_md5:{user.id}:{blob_path}:{stat.st_size}:{stat.st_mtime}"
    )
    cached = await async_cache.get(cache_key)
    if cached:
        return cached.decode() if isinstance(cached, bytes) else str(cached)

    digest = await fs_cloud_sync_blob_handler.compute_file_md5(
        user_blob_path(user, blob_path)
    )
    if digest:
        await async_cache.set(cache_key, digest, ex=_HASH_CACHE_TTL_SECONDS)

    return digest


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


def resolve_rom(game_name: str, can_see: Callable[[Rom], bool]) -> Rom | None:
    """The ROM a cloud-sync file belongs to, matched on file name alone.

    When several platforms hold a ROM of the same name the match is ambiguous;
    the first candidate wins so it stays stable across syncs.
    """
    for rom in db_rom_handler.get_roms_by_fs_name_no_ext(game_name):
        if can_see(rom):
            return rom

    return None


async def asset_md5(asset: Save | State | Screenshot) -> str | None:
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
    growing pile of files no core would ever load. States have no such
    `slot` column, so they're grouped into RetroArch's own numbered slots by
    file-name suffix instead (`group_states_by_slot`) -- the newest state in
    each (rom, emulator, slot) bucket is surfaced under the canonical name
    RetroArch itself would use, regardless of who actually created it.
    """
    entries: list[dict[str, str]] = []

    for save in db_save_handler.get_saves(user_id=user.id):
        if save.slot is not None or save.missing_from_fs or not can_see(save.rom):
            continue

        digest = await asset_md5(save)
        if not digest:
            continue

        entries.append(
            {
                "path": build_cloud_sync_path("saves", save.emulator, save.file_name),
                "hash": digest,
            }
        )

    states_by_slot = group_states_by_slot(db_state_handler.get_states(user_id=user.id))
    for (_rom_id, emulator, slot_suffix), state in states_by_slot.items():
        if state.missing_from_fs or not can_see(state.rom):
            continue

        digest = await asset_md5(state)
        if not digest:
            continue

        file_name = canonical_state_file_name(state.rom, slot_suffix)
        entries.append(
            {
                "path": build_cloud_sync_path("states", emulator, file_name),
                "hash": digest,
            }
        )

        screenshot = state.screenshot
        if screenshot and not screenshot.missing_from_fs:
            screenshot_digest = await asset_md5(screenshot)
            if screenshot_digest:
                entries.append(
                    {
                        "path": build_cloud_sync_path(
                            "states", emulator, f"{file_name}.png"
                        ),
                        "hash": screenshot_digest,
                    }
                )

    entries += await build_blob_manifest_entries(user)

    entries.sort(key=lambda entry: entry["path"])
    return entries
