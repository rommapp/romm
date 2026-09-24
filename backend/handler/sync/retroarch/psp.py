"""RetroArch Cloud Sync of PPSSPP's ``saves/[<core>/]PSP/SAVEDATA/<folder>/`` layout.

Each folder's files only make sense as a set, so they are stored as one zipped ``Save``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import struct
import zipfile
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable
from contextlib import suppress
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

from redis.exceptions import RedisError

from config import SYNC_RETROARCH_PSP_PENDING_PATH, SYNC_RETROARCH_PSP_SERIAL_MAP
from handler.database import db_platform_handler, db_rom_handler, db_save_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.base_handler import FSHandler
from handler.redis_handler import async_cache
from handler.sync.retroarch import sync_handler
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save
from models.rom import Rom
from models.user import User
from utils.memory_cards import content_hash_of_bytes
from utils.zip_cache import ensure_zipfile_writable

_IGNORED_CATEGORY = "SYSTEM"
_SAVEDATA_CATEGORY = "SAVEDATA"

# Real PSP save folders hold a handful of small files; anything past these is
# not one, and inflating it on every manifest build would exhaust memory.
_BUNDLE_MAX_MEMBERS = 64
BUNDLE_MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024

_BUNDLE_FOLDER_PATTERN = re.compile(r"^PSP-(.+?)(?: \[.*])?\.zip$")

fs_psp_pending_handler = FSHandler(base_path=SYNC_RETROARCH_PSP_PENDING_PATH)


class PspFolderUnresolved(Exception):
    """A save folder no ROM matches yet; its files wait on disk until one does."""


class PspBundleInvalid(Exception):
    """The folder's bundle is unreadable, or the upload would push it past the limits."""


@dataclass(frozen=True)
class PspFilePath:
    """A parsed ``saves/[<emulator>/]PSP/SAVEDATA/<save_folder>/<file_name>`` path."""

    emulator: str | None
    save_folder: str
    file_name: str


def resolve_psp_path(file_path: str) -> PspFilePath | Literal["ignore"] | None:
    """A PSP save-folder file, ``"ignore"`` for engine caches, or None for any other path."""
    segments = sync_handler.split_segments(file_path)
    if segments is None or len(segments) < 3 or segments[0] != "saves":
        return None

    # Without "sort saves by core", PPSSPP's memory stick sits at the saves root.
    categories = (_IGNORED_CATEGORY, _SAVEDATA_CATEGORY)
    if segments[1].upper() == "PSP" and segments[2].upper() in categories:
        emulator, rest = None, segments[2:]
    elif len(segments) >= 4 and segments[2].upper() == "PSP":
        emulator, rest = sync_handler.emulator_from_dir_name(segments[1]), segments[3:]
        if emulator is None:
            return None
    else:
        return None

    category = rest[0].upper()
    if category == _IGNORED_CATEGORY:
        return "ignore"
    if category != _SAVEDATA_CATEGORY:
        return None
    if len(rest) < 3:
        return None

    return PspFilePath(
        emulator=emulator,
        save_folder=rest[1],
        file_name="/".join(rest[2:]),
    )


def _bundle_base_name(save_folder: str) -> str:
    return f"PSP-{save_folder}.zip"


def _bundle_folder(file_name: str) -> str | None:
    """The save folder a bundle file name (optionally ` [tag]`-suffixed) holds."""
    match = _BUNDLE_FOLDER_PATTERN.match(file_name)
    return match.group(1) if match else None


def is_psp_bundle_file_name(file_name: str) -> bool:
    return _bundle_folder(file_name) is not None


def _latest_bundles_by_folder(
    saves: Iterable[Save], can_see: Callable[[Rom], bool]
) -> dict[str, Save]:
    """The newest visible bundle per folder, since a folder path carries no ROM."""
    latest: dict[str, Save] = {}
    for save in saves:
        save_folder = _bundle_folder(save.file_name)
        if save_folder is None or not can_see(save.rom):
            continue
        current = latest.get(save_folder)
        if current is None or sync_handler.recency_key(save) > sync_handler.recency_key(
            current
        ):
            latest[save_folder] = save

    return latest


def _find_bundle_by_folder(
    user: User, save_folder: str, can_see: Callable[[Rom], bool]
) -> Save | None:
    saves = db_save_handler.get_saves(
        user_id=user.id,
        slot_is_null=True,
        file_name_prefix=_bundle_base_name(save_folder).removesuffix(".zip"),
    )
    return _latest_bundles_by_folder(saves, can_see).get(save_folder)


def _derive_serial(save_folder: str) -> str:
    return re.sub(r"DATA\d+$", "", save_folder, flags=re.IGNORECASE)


def _normalize_title(s: str) -> str:
    """A title reduced to lowercase alphanumeric words, so a PARAM.SFO TITLE
    matches RomM's filename-derived one despite punctuation and casing."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def parse_sfo(data: bytes) -> dict[str, str | int]:
    """The fields of a PSP PARAM.SFO file, which describes a save folder.

    Raises:
        ValueError: The data is not a well-formed PARAM.SFO.
    """
    if len(data) < 20 or data[0:4] != b"\x00PSF":
        raise ValueError("Not a PARAM.SFO file (bad magic)")

    try:
        return _parse_sfo_tables(data)
    except struct.error as exc:
        raise ValueError(f"Truncated PARAM.SFO file: {exc}") from exc


def _parse_sfo_tables(data: bytes) -> dict[str, str | int]:
    key_table_offset, data_table_offset, entry_count = struct.unpack_from(
        "<III", data, 8
    )

    result: dict[str, str | int] = {}
    for i in range(entry_count):
        entry_offset = 20 + i * 16
        key_offset, data_fmt = struct.unpack_from("<HH", data, entry_offset)
        (data_len,) = struct.unpack_from("<I", data, entry_offset + 8)
        (data_offset,) = struct.unpack_from("<I", data, entry_offset + 12)

        key_start = key_table_offset + key_offset
        key_end = data.find(b"\x00", key_start)
        key = data[key_start : key_end if key_end != -1 else None].decode("ascii")

        value_start = data_table_offset + data_offset
        raw_value = data[value_start : value_start + data_len]

        # 0x0404 = int32, 0x0204/0x0402 = UTF-8 string (NUL-padded/terminated).
        if data_fmt == 0x0404:
            result[key] = (
                struct.unpack_from("<i", raw_value)[0] if len(raw_value) >= 4 else 0
            )
        else:
            nul = raw_value.find(b"\x00")
            result[key] = raw_value[: nul if nul != -1 else None].decode(
                "utf-8", errors="replace"
            )

    return result


def _match_by_normalized_title(
    title: str, can_see: Callable[[Rom], bool]
) -> Rom | None:
    # Searching on the raw title would hand punctuation-glued words like
    # "-FINAL" to the ILIKE fallback, which then never matches.
    target = _normalize_title(title)
    if not target:
        return None

    platform = db_platform_handler.get_platform_by_fs_slug("psp")
    platform_ids = [platform.id] if platform else None
    candidates = [
        rom
        for rom in db_rom_handler.get_roms_scalar(
            search_term=target, platform_ids=platform_ids
        )
        if can_see(rom)
    ]

    for attr in ("fs_name_no_tags", "name", "fs_name_no_ext"):
        for rom in candidates:
            value = getattr(rom, attr, None)
            if value and _normalize_title(value) == target:
                return rom

    return None


def _resolve_rom(
    save_folder: str, sfo_title: str | None, can_see: Callable[[Rom], bool]
) -> Rom | None:
    """The ROM a save folder belongs to, via SYNC_RETROARCH_PSP_SERIAL_MAP, else its PARAM.SFO title."""
    serial = _derive_serial(save_folder)
    mapped_title = SYNC_RETROARCH_PSP_SERIAL_MAP.get(serial)
    if mapped_title:
        rom = sync_handler.resolve_rom(mapped_title, can_see)
        if rom:
            return rom
        log.warning(
            f"SYNC_RETROARCH_PSP_SERIAL_MAP entry for {hl(serial)} ({hl(mapped_title)}) "
            "didn't match any rom in the library"
        )

    if sfo_title:
        rom = _match_by_normalized_title(sfo_title, can_see)
        if rom:
            log.info(
                f"Resolved PSP save folder {hl(save_folder)} via PARAM.SFO "
                f"title {hl(sfo_title)} to {hl(str(rom.name))}"
            )
            return rom
        log.warning(
            f"Couldn't auto-match PARAM.SFO title {hl(sfo_title)} for PSP save "
            f"folder {hl(save_folder)}; add serial {hl(serial)} to "
            "SYNC_RETROARCH_PSP_SERIAL_MAP if this keeps happening"
        )

    return None


def _exceeds_bundle_limits(member_sizes: Collection[int]) -> bool:
    return (
        len(member_sizes) > _BUNDLE_MAX_MEMBERS
        or sum(member_sizes) > BUNDLE_MAX_UNCOMPRESSED_BYTES
    )


def _load_bundle_entries(
    path: Path, names: Collection[str] | None = None
) -> dict[str, bytes]:
    """The bundle's members by name, only those in `names` when given.

    Raises:
        FileNotFoundError: The bundle file is gone.
        zipfile.BadZipFile: The bundle is corrupt or exceeds the bundle limits.
    """
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        if _exceeds_bundle_limits([info.file_size for info in infos]):
            raise zipfile.BadZipFile("PSP bundle exceeds the size limits")
        # `read` stops at each member's declared size, so the check above holds.
        return {
            info.filename: zf.read(info)
            for info in infos
            if names is None or info.filename in names
        }


def _load_bundle_member_names(path: Path) -> list[str]:
    """The bundle's member names, read from its central directory without inflating.

    Raises:
        FileNotFoundError: The bundle file is gone.
        zipfile.BadZipFile: The bundle is corrupt or exceeds the bundle limits.
    """
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        if _exceeds_bundle_limits([info.file_size for info in infos]):
            raise zipfile.BadZipFile("PSP bundle exceeds the size limits")
        return [info.filename for info in infos]


def _write_bundle(entries: dict[str, bytes]) -> bytes:
    # `zipfile_inflate64` is imported elsewhere for ROM archive reading, and
    # breaks `writestr()` until this runs.
    ensure_zipfile_writable()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buffer.getvalue()


async def _load_bundle(
    bundle: Save, names: Collection[str] | None = None
) -> dict[str, bytes]:
    """`_load_bundle_entries` for a bundle row, off the event loop."""
    path = fs_asset_handler.validate_path(bundle.full_path)
    return await asyncio.to_thread(_load_bundle_entries, path, names)


# RomM runs a single worker, so in-process locks serialize each folder's
# read-modify-write; multiple workers would need a distributed lock.
_folder_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


async def _resolve_folder_rom(
    info: PspFilePath,
    content: bytes,
    pending_dir: str,
    can_see: Callable[[Rom], bool],
) -> Rom:
    """The ROM a save folder with no bundle yet belongs to.

    Raises:
        PspFolderUnresolved: No ROM matches yet; `content` is buffered instead.
    """
    sfo_title = None
    if info.file_name.upper() == "PARAM.SFO":
        try:
            title = parse_sfo(content).get("TITLE")
        except ValueError as exc:
            log.warning(f"Failed to parse PARAM.SFO: {exc}")
        else:
            sfo_title = title if isinstance(title, str) else None

    rom = _resolve_rom(info.save_folder, sfo_title, can_see)
    if rom:
        return rom

    await fs_psp_pending_handler.write_file(
        file=content, path=pending_dir, filename=info.file_name
    )
    log.warning(
        f"No rom found yet for PSP save folder {hl(info.save_folder)} "
        f"(serial {hl(_derive_serial(info.save_folder))}), buffered "
        f"{hl(info.file_name)} until it resolves (e.g. PARAM.SFO arrives)"
    )
    raise PspFolderUnresolved(info.save_folder)


async def _add_bundle(
    user: User, info: PspFilePath, rom: Rom, entries: dict[str, bytes]
) -> None:
    bundle_path = fs_asset_handler.build_saves_file_path(
        user=user,
        platform_fs_slug=rom.platform.fs_slug,
        rom_id=rom.id,
        emulator=info.emulator,
    )
    bundle_name = _bundle_base_name(info.save_folder)
    zip_bytes = await asyncio.to_thread(_write_bundle, entries)
    await fs_asset_handler.write_file(
        file=zip_bytes, path=bundle_path, filename=bundle_name
    )
    added = db_save_handler.add_save(
        Save(
            rom_id=rom.id,
            user_id=user.id,
            file_name=bundle_name,
            file_path=bundle_path,
            file_size_bytes=len(zip_bytes),
            content_hash=content_hash_of_bytes(zip_bytes),
            emulator=info.emulator,
            slot=None,
        )
    )
    # The merged instance keeps the Python-side `updated_at`, which the
    # database may store truncated, so the cache key is built from a re-read.
    bundle = db_save_handler.get_save(user_id=user.id, id=added.id)
    if bundle:
        await _prime_member_md5s(bundle, entries)


async def put_psp_file(
    user: User, info: PspFilePath, content: bytes, can_see: Callable[[Rom], bool]
) -> None:
    """Merge one uploaded file into its save folder's bundle.

    Raises:
        PspFolderUnresolved: No ROM matches the folder yet; the file is buffered.
        PspBundleInvalid: The bundle is unreadable or would exceed the limits.
    """
    # PPSSPP writes a folder as a burst of PUTs, so the bundle is rewritten in
    # place rather than keeping each partial merge as save history.
    async with _folder_locks[f"{user.id}:{info.save_folder}"]:
        pending_dir = f"{user.id}/{info.save_folder}"
        existing = _find_bundle_by_folder(user, info.save_folder, can_see)

        merged: dict[str, bytes] = {}
        if existing:
            try:
                merged = await _load_bundle(existing)
            except FileNotFoundError:
                log.warning(f"PSP bundle {hl(existing.full_path)} is gone, rebuilding")
            except zipfile.BadZipFile as exc:
                raise PspBundleInvalid(existing.full_path) from exc
        else:
            rom = await _resolve_folder_rom(info, content, pending_dir, can_see)

        try:
            pending_names = await fs_psp_pending_handler.list_files(pending_dir)
        except FileNotFoundError:
            pending_names = []
        for name in pending_names:
            merged[name] = await fs_psp_pending_handler.read_file(
                f"{pending_dir}/{name}"
            )
        merged[info.file_name] = content
        if _exceeds_bundle_limits([len(data) for data in merged.values()]):
            raise PspBundleInvalid(info.save_folder)

        if existing:
            await _rewrite_bundle(existing, merged)
        else:
            await _add_bundle(user, info, rom, merged)

        for name in pending_names:
            with suppress(FileNotFoundError):
                await fs_psp_pending_handler.remove_file(f"{pending_dir}/{name}")


async def _rewrite_bundle(bundle: Save, entries: dict[str, bytes]) -> None:
    """Write `entries` over the bundle's own file and refresh its row."""
    zip_bytes = await asyncio.to_thread(_write_bundle, entries)
    await fs_asset_handler.write_file(
        file=zip_bytes, path=bundle.file_path, filename=bundle.file_name
    )
    updated = db_save_handler.update_save(
        bundle.id,
        {
            "file_size_bytes": len(zip_bytes),
            "content_hash": content_hash_of_bytes(zip_bytes),
            "missing_from_fs": False,
        },
    )
    await _prime_member_md5s(updated, entries)


async def _read_bundle(
    bundle: Save, names: Collection[str] | None = None
) -> dict[str, bytes] | None:
    try:
        return await _load_bundle(bundle, names)
    except (FileNotFoundError, zipfile.BadZipFile) as exc:
        log.warning(f"Failed to read PSP bundle {hl(bundle.full_path)}: {exc}")
        return None


async def get_psp_file(
    user: User, info: PspFilePath, can_see: Callable[[Rom], bool]
) -> bytes | None:
    bundle = _find_bundle_by_folder(user, info.save_folder, can_see)
    if not bundle:
        return None
    entries = await _read_bundle(bundle, {info.file_name})
    return entries.get(info.file_name) if entries else None


async def delete_psp_file(
    user: User, info: PspFilePath, can_see: Callable[[Rom], bool]
) -> None:
    """Drop one member from its folder's bundle, and the bundle once empty."""
    async with _folder_locks[f"{user.id}:{info.save_folder}"]:
        bundle = _find_bundle_by_folder(user, info.save_folder, can_see)
        if not bundle:
            return

        # An unreadable bundle is kept rather than dropped along with every
        # other member it holds.
        entries = await _read_bundle(bundle)
        if entries is None or info.file_name not in entries:
            return

        del entries[info.file_name]
        if entries:
            await _rewrite_bundle(bundle, entries)
            return

        db_save_handler.delete_save(bundle.id)
        with suppress(FileNotFoundError):
            await fs_asset_handler.remove_file(file_path=bundle.full_path)


def _member_md5s_cache_key(bundle: Save) -> str:
    return (
        f"romm:retroarch_sync:psp_member_md5s:{bundle.full_path}"
        f":{bundle.content_hash}:{bundle.updated_at.timestamp()}"
    )


def _member_md5s(members: dict[str, bytes]) -> dict[str, str]:
    return {
        name: hashlib.md5(data, usedforsecurity=False).hexdigest()
        for name, data in members.items()
    }


async def _prime_member_md5s(bundle: Save, members: dict[str, bytes]) -> None:
    """Cache a just-written bundle's member MD5s, so the next manifest skips inflating it."""
    # Best effort: the bundle is already written, and a miss is recomputed later.
    try:
        await async_cache.set(
            _member_md5s_cache_key(bundle),
            json.dumps(_member_md5s(members)),
            ex=sync_handler.HASH_CACHE_TTL_SECONDS,
        )
    except RedisError as exc:
        log.warning(
            f"Failed to cache PSP bundle hashes for {hl(bundle.full_path)}: {exc}"
        )


async def _bundle_member_md5s(bundle: Save) -> dict[str, str] | None:
    """Each member's MD5, cached so a manifest build doesn't inflate every bundle."""
    cached = await async_cache.get(_member_md5s_cache_key(bundle))
    if cached:
        return json.loads(cached)

    members = await _read_bundle(bundle)
    if members is None:
        return None

    await _prime_member_md5s(bundle, members)
    return _member_md5s(members)


def _member_sync_path(bundle: Save, save_folder: str, member_name: str) -> str:
    return sync_handler.build_retroarch_sync_path(
        "saves", bundle.emulator, f"PSP/SAVEDATA/{save_folder}/{member_name}"
    )


async def list_psp_member_paths(
    saves: Iterable[Save], can_see: Callable[[Rom], bool]
) -> list[str]:
    """The manifest path of each bundle member, without inflating any bundle."""
    paths: list[str] = []
    for save_folder, save in _latest_bundles_by_folder(saves, can_see).items():
        if save.missing_from_fs:
            continue
        try:
            path = fs_asset_handler.validate_path(save.full_path)
            names = await asyncio.to_thread(_load_bundle_member_names, path)
        except (ValueError, FileNotFoundError, zipfile.BadZipFile) as exc:
            log.warning(f"Failed to read PSP bundle {hl(save.full_path)}: {exc}")
            continue
        paths += [_member_sync_path(save, save_folder, name) for name in names]

    return paths


async def build_psp_manifest_entries(
    saves: Iterable[Save], can_see: Callable[[Rom], bool]
) -> list[dict[str, str]]:
    """One manifest entry per bundle member, since RetroArch diffs per file."""
    entries: list[dict[str, str]] = []
    for save_folder, save in _latest_bundles_by_folder(saves, can_see).items():
        if save.missing_from_fs:
            continue
        digests = await _bundle_member_md5s(save)
        if digests is None:
            continue

        entries += [
            {"path": _member_sync_path(save, save_folder, name), "hash": digest}
            for name, digest in digests.items()
        ]

    return entries
