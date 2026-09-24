"""RetroArch Cloud Sync support for PPSSPP's PSP save-folder layout.

PPSSPP mirrors a memory stick under ``saves/[<core>/]PSP/``: each
``SAVEDATA/<folder>/`` holds several files that only make sense as a set, so
they're bundled into one zip stored as a single RomM ``Save``. ``SYSTEM/``
holds engine caches only and is ignored.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import struct
import zipfile
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable
from contextlib import suppress
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from config import CLOUD_SYNC_PSP_PENDING_PATH, PSP_SERIAL_MAP
from handler import cloud_sync_handler
from handler.cloud_sync_emulator_names import to_romm_emulator
from handler.database import db_platform_handler, db_rom_handler, db_save_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.assets_handler import hash_zip_contents
from handler.filesystem.base_handler import FSHandler
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save
from models.rom import Rom
from models.user import User
from utils.zip_cache import ensure_zipfile_writable

_IGNORED_CATEGORY = "SYSTEM"
_SAVEDATA_CATEGORY = "SAVEDATA"

# Real PSP save folders hold a handful of small files; anything past these is
# not one, and inflating it on every manifest build would exhaust memory.
_BUNDLE_MAX_MEMBERS = 64
_BUNDLE_MAX_UNCOMPRESSED_BYTES = 64 * 1024 * 1024

_BUNDLE_FOLDER_PATTERN = re.compile(r"^PSP-(.+?)(?: \[.*])?\.zip$")

fs_psp_pending_handler = FSHandler(base_path=CLOUD_SYNC_PSP_PENDING_PATH)


class PspFolderUnresolved(Exception):
    """A save folder no ROM matches yet; its files wait on disk until one does."""


@dataclass(frozen=True)
class PspFilePath:
    """A parsed ``saves/[<emulator>/]PSP/SAVEDATA/<save_folder>/<file_name>`` path."""

    emulator: str | None
    save_folder: str
    file_name: str


def resolve_psp_path(file_path: str) -> PspFilePath | Literal["ignore"] | None:
    """A PSP save-folder file, ``"ignore"`` for engine caches, or None for any other path."""
    segments = cloud_sync_handler.split_segments(file_path)
    if segments is None or len(segments) < 3 or segments[0] != "saves":
        return None

    # Without "sort saves by core", PPSSPP's memory stick sits at the saves root.
    categories = (_IGNORED_CATEGORY, _SAVEDATA_CATEGORY)
    if segments[1].upper() == "PSP" and segments[2].upper() in categories:
        emulator, rest = None, segments[2:]
    elif len(segments) >= 4 and segments[2].upper() == "PSP":
        emulator, rest = to_romm_emulator(segments[1]), segments[3:]
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
    """The bundle each folder path resolves to for the manifest and GET/PUT/DELETE,
    the newest visible unslotted one, since a folder path carries no ROM."""
    latest: dict[str, Save] = {}
    for save in saves:
        save_folder = _bundle_folder(save.file_name)
        if save_folder is None or save.slot is not None or not can_see(save.rom):
            continue
        current = latest.get(save_folder)
        if current is None or cloud_sync_handler.recency_key(
            save
        ) > cloud_sync_handler.recency_key(current):
            latest[save_folder] = save

    return latest


def _find_bundle_by_folder(
    user: User, save_folder: str, can_see: Callable[[Rom], bool]
) -> Save | None:
    saves = db_save_handler.get_saves(user_id=user.id, slot_is_null=True)
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
    """The ROM a save folder belongs to, via PSP_SERIAL_MAP, else its PARAM.SFO title."""
    serial = _derive_serial(save_folder)
    mapped_title = PSP_SERIAL_MAP.get(serial)
    if mapped_title:
        rom = cloud_sync_handler.resolve_rom(mapped_title, can_see)
        if rom:
            return rom
        log.warning(
            f"PSP_SERIAL_MAP entry for {hl(serial)} ({hl(mapped_title)}) "
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
            "PSP_SERIAL_MAP if this keeps happening"
        )

    return None


def _load_bundle_entries(
    zip_bytes: bytes, names: Collection[str] | None = None
) -> dict[str, bytes]:
    """The bundle's members by name, only those in `names` when given.

    Raises:
        zipfile.BadZipFile: The bundle is corrupt or exceeds the bundle limits.
    """
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        infos = zf.infolist()
        if len(infos) > _BUNDLE_MAX_MEMBERS or (
            sum(info.file_size for info in infos) > _BUNDLE_MAX_UNCOMPRESSED_BYTES
        ):
            raise zipfile.BadZipFile("PSP bundle exceeds the size limits")
        # `read` stops at each member's declared size, so the check above holds.
        return {
            info.filename: zf.read(info)
            for info in infos
            if names is None or info.filename in names
        }


def _write_bundle(entries: dict[str, bytes]) -> bytes:
    # `zipfile_inflate64` is imported elsewhere for ROM archive reading, and
    # breaks `writestr()` until this runs.
    ensure_zipfile_writable()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def _bundle_content_hash(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        return hash_zip_contents(zf)


def _pending_dir(user: User, save_folder: str) -> str:
    return f"{user.id}/{save_folder}"


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
    zip_bytes = _write_bundle(entries)
    await fs_asset_handler.write_file(
        file=zip_bytes, path=bundle_path, filename=bundle_name
    )
    db_save_handler.add_save(
        Save(
            rom_id=rom.id,
            user_id=user.id,
            file_name=bundle_name,
            file_path=bundle_path,
            file_size_bytes=len(zip_bytes),
            content_hash=_bundle_content_hash(zip_bytes),
            emulator=info.emulator,
            slot=None,
        )
    )


async def put_psp_file(
    user: User, info: PspFilePath, content: bytes, can_see: Callable[[Rom], bool]
) -> None:
    """Merge one uploaded file into its save folder's bundle.

    Raises:
        PspFolderUnresolved: No ROM matches the folder yet; the file is buffered.
    """
    # PPSSPP writes a folder as a burst of PUTs, so the bundle is rewritten in
    # place rather than keeping each partial merge as save history.
    async with _folder_locks[f"{user.id}:{info.save_folder}"]:
        pending_dir = _pending_dir(user, info.save_folder)
        existing = _find_bundle_by_folder(user, info.save_folder, can_see)

        merged: dict[str, bytes] = {}
        if existing:
            try:
                zip_bytes = await fs_asset_handler.read_file(existing.full_path)
            except FileNotFoundError:
                log.warning(f"PSP bundle {hl(existing.full_path)} is gone, rebuilding")
            else:
                merged = _load_bundle_entries(zip_bytes)
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

        if existing:
            await _rewrite_bundle(existing, merged)
        else:
            await _add_bundle(user, info, rom, merged)

        for name in pending_names:
            with suppress(FileNotFoundError):
                await fs_psp_pending_handler.remove_file(f"{pending_dir}/{name}")


async def _rewrite_bundle(bundle: Save, entries: dict[str, bytes]) -> None:
    """Write `entries` over the bundle's own file and refresh its row."""
    zip_bytes = _write_bundle(entries)
    await fs_asset_handler.write_file(
        file=zip_bytes, path=bundle.file_path, filename=bundle.file_name
    )
    db_save_handler.update_save(
        bundle.id,
        {
            "file_size_bytes": len(zip_bytes),
            "content_hash": _bundle_content_hash(zip_bytes),
            "missing_from_fs": False,
        },
    )


async def _read_bundle(
    bundle: Save, names: Collection[str] | None = None
) -> dict[str, bytes] | None:
    try:
        return _load_bundle_entries(
            await fs_asset_handler.read_file(bundle.full_path), names
        )
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
    """Drops one member from its folder's bundle, and the bundle once empty.

    A missing bundle or member is a no-op, like every other cloud-sync delete.
    """
    async with _folder_locks[f"{user.id}:{info.save_folder}"]:
        bundle = _find_bundle_by_folder(user, info.save_folder, can_see)
        if not bundle:
            return

        entries = await _read_bundle(bundle) or {}
        if entries and info.file_name not in entries:
            return

        entries.pop(info.file_name, None)
        if entries:
            await _rewrite_bundle(bundle, entries)
            return

        db_save_handler.delete_save(bundle.id)
        with suppress(FileNotFoundError):
            await fs_asset_handler.remove_file(file_path=bundle.full_path)


async def build_psp_manifest_entries(
    saves: Iterable[Save], can_see: Callable[[Rom], bool]
) -> list[dict[str, str]]:
    """One manifest entry per bundle member, since RetroArch diffs per file."""
    entries: list[dict[str, str]] = []
    for save_folder, save in _latest_bundles_by_folder(saves, can_see).items():
        if save.missing_from_fs:
            continue
        members = await _read_bundle(save)
        if members is None:
            continue

        for member_name, data in members.items():
            entries.append(
                {
                    "path": cloud_sync_handler.build_cloud_sync_path(
                        "saves",
                        save.emulator,
                        f"PSP/SAVEDATA/{save_folder}/{member_name}",
                    ),
                    "hash": hashlib.md5(data, usedforsecurity=False).hexdigest(),
                }
            )

    return entries
