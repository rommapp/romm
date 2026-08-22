"""RetroArch Cloud Sync support for PPSSPP's PSP save-folder layout.

PPSSPP (the PSP core) doesn't save a single file per game like every other
core -- it mirrors a real PSP's memory stick layout under RetroArch's own
saves directory: ``saves/<core>/PSP/SAVEDATA/<slot>/`` holds several small
files (PARAM.SFO, the actual save data, ICON0.PNG, PIC1.PNG, ...) that only
make sense as a set, plus ``saves/<core>/PSP/SYSTEM/CACHE/`` holds pure
engine caches (shader caches etc.) with no save data at all.

This mirrors the retroarch-webdav-romm shim's ``pspSave.ts``: a save
folder's files are bundled into a single zip stored as one RomM ``Save``,
and unbundled again for GET/manifest purposes -- everywhere else in
cloud sync, "one WebDAV path = one RomM asset" holds, but it doesn't here.
"""

from __future__ import annotations

import asyncio
import re
import struct
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from config import CLOUD_SYNC_PSP_PENDING_PATH, PSP_SERIAL_MAP
from handler.cloud_sync_emulator_names import to_retroarch_dir_name
from utils.zip_cache import _ensure_zipfile_writable
from handler.database import db_platform_handler, db_rom_handler, db_save_handler
from handler.filesystem import fs_asset_handler
from handler.filesystem.base_handler import FSHandler
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save
from models.rom import Rom
from models.user import User

_IGNORED_CATEGORY = "SYSTEM"
_SAVEDATA_CATEGORY = "SAVEDATA"

fs_psp_pending_handler = FSHandler(base_path=CLOUD_SYNC_PSP_PENDING_PATH)


class PspFolderUnresolved(Exception):
    """A PSP save folder's files arrived but couldn't (yet) be matched to a
    rom -- buffered on disk until a later file (usually PARAM.SFO) resolves
    it, or forever if it never does (add it to PSP_SERIAL_MAP)."""


@dataclass(frozen=True)
class PspFilePath:
    """A parsed ``saves/<emulator>/PSP/SAVEDATA/<save_folder>/<file_name>``
    cloud-sync path."""

    emulator: str
    save_folder: str
    file_name: str


def resolve_psp_path(file_path: str) -> PspFilePath | Literal["ignore"] | None:
    """Classifies a ``saves/...`` cloud-sync path as a PSP save-folder file,
    PSP engine-cache noise to ignore, or neither (a normal single-file save
    -- None, let the generic save/state path handle it)."""
    segments = [s for s in file_path.strip("/").split("/") if s]
    if len(segments) < 4 or segments[0] != "saves":
        return None
    if segments[2].upper() != "PSP":
        return None

    category = segments[3].upper()
    if category == _IGNORED_CATEGORY:
        return "ignore"
    if category != _SAVEDATA_CATEGORY:
        return None
    if len(segments) < 6:
        return None

    return PspFilePath(
        emulator=segments[1],
        save_folder=segments[4],
        file_name="/".join(segments[5:]),
    )


def _bundle_base_name(save_folder: str) -> str:
    return f"PSP-{save_folder}.zip"


def is_psp_bundle_file_name(file_name: str) -> bool:
    """Whether a stored save's file name is a PSP bundle -- used by
    `build_manifest` to exclude these from normal single-file save
    handling."""
    return re.match(r"^PSP-.+\.zip$", file_name) is not None


def _bundle_pattern(save_folder: str) -> re.Pattern[str]:
    """Matches a stored bundle filename by prefix/suffix only, tolerating
    whatever else ends up between them -- there is nothing else to key on,
    since bundles are update-in-place (one row per save folder), not
    history-preserving."""
    return re.compile(rf"^PSP-{re.escape(save_folder)}\b.*\.zip$")


def _find_bundle_by_folder(user: User, save_folder: str) -> Save | None:
    """Finds the current bundle for a save folder by its name alone -- the
    folder name (e.g. "ULUS10336DATA0") is already a globally unique
    identifier for a given game+slot, so this works without ever needing
    PSP_SERIAL_MAP or PARAM.SFO except on the very first upload of a new
    folder."""
    pattern = _bundle_pattern(save_folder)
    saves = db_save_handler.get_saves(user_id=user.id)
    candidates = [s for s in saves if pattern.match(s.file_name)]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.updated_at, s.id))


def _derive_serial(save_folder: str) -> str:
    return re.sub(r"DATA\d+$", "", save_folder, flags=re.IGNORECASE)


def _normalize_title(s: str) -> str:
    """Loose title comparison for matching a PARAM.SFO TITLE (e.g. "CRISIS
    CORE -FINAL FANTASY VII-") against RomM's filename-derived titles (e.g.
    "Crisis Core - Final Fantasy VII (USA)") -- collapses both down to bare
    alphanumerics so punctuation/casing/spacing differences (the norm
    between PSF titles and filename-derived ones) don't block an otherwise
    obvious match."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def parse_sfo(data: bytes) -> dict[str, str | int]:
    """Minimal parser for the PSP's PARAM.SFO ("PSF") format -- the file
    PPSSPP writes into every save folder describing that save. Only two of
    its fields matter here: DISC_ID (the game's serial, e.g. "ULUS10336")
    and TITLE (the game's display name), to resolve a save folder to a RomM
    rom.

    Format: a 20-byte header, a fixed-size index table (one 16-byte entry
    per key), a key table (NUL-terminated ASCII strings), and a data table
    (UTF-8 strings or little-endian integers, per entry).
    """
    if len(data) < 20 or data[0:4] != b"\x00PSF":
        raise ValueError("Not a PARAM.SFO file (bad magic)")

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
            result[key] = struct.unpack_from("<i", raw_value)[0] if len(raw_value) >= 4 else 0
        else:
            nul = raw_value.find(b"\x00")
            result[key] = raw_value[: nul if nul != -1 else None].decode(
                "utf-8", errors="replace"
            )

    return result


def _match_by_normalized_title(
    title: str, can_see: Callable[[Rom], bool]
) -> Rom | None:
    platform = db_platform_handler.get_platform_by_fs_slug("psp")
    platform_ids = [platform.id] if platform else None
    candidates = [
        rom
        for rom in db_rom_handler.get_roms_scalar(
            search_term=title, platform_ids=platform_ids
        )
        if can_see(rom)
    ]

    target = _normalize_title(title)
    for attr in ("fs_name_no_tags", "name", "fs_name_no_ext"):
        for rom in candidates:
            value = getattr(rom, attr, None)
            if value and _normalize_title(value) == target:
                return rom

    return None


def _resolve_rom(
    save_folder: str, sfo_title: str | None, can_see: Callable[[Rom], bool]
) -> Rom | None:
    """Resolves a PSP save folder to a RomM rom. Tries the PARAM.SFO title
    first -- it's already sent as part of every save, so this is what makes
    PSP saves sync automatically with zero manual setup for the common
    case. PSP_SERIAL_MAP is an explicit override checked first when
    present, and the fallback when SFO title matching doesn't find
    anything -- some games' PSF titles are abbreviated/stylized enough that
    normalization alone won't bridge the gap to RomM's filename-derived
    title."""
    serial = _derive_serial(save_folder)
    mapped_title = PSP_SERIAL_MAP.get(serial)
    if mapped_title:
        candidates = [
            rom
            for rom in db_rom_handler.get_roms_by_fs_name_no_ext(mapped_title)
            if can_see(rom)
        ]
        if candidates:
            return candidates[0]
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
            f"folder {hl(save_folder)} -- add serial {hl(serial)} to "
            "PSP_SERIAL_MAP if this keeps happening"
        )

    return None


def _load_bundle_entries(zip_bytes: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def _write_bundle(entries: dict[str, bytes]) -> bytes:
    # `zipfile_inflate64` (pulled in elsewhere for ROM archive reading)
    # replaces `zipfile._get_compressor` with a signature CPython 3.13's
    # own `ZipFile.writestr()` can't call -- see `_ensure_zipfile_writable`.
    _ensure_zipfile_writable()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buffer.getvalue()


def _pending_dir(user: User, save_folder: str) -> str:
    return f"{user.id}/{save_folder}"




# Per-(user, save folder) locks. FastAPI/uvicorn typically runs this as a
# single worker process for a RomM instance, so an in-process asyncio.Lock
# is enough to serialize the read-modify-write over a folder's bundle the
# same way the shim's single-threaded Node process naturally did --
# concurrent multi-worker deployments would need a distributed lock
# instead, which nothing else in cloud sync uses either.
_folder_locks: dict[str, asyncio.Lock] = {}


def _get_folder_lock(key: str) -> asyncio.Lock:
    lock = _folder_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _folder_locks[key] = lock
    return lock


async def put_psp_file(
    user: User, info: PspFilePath, content: bytes, can_see: Callable[[Rom], bool]
) -> None:
    """Merges one uploaded file into its save folder's bundle and
    re-uploads it. Deliberately does not preserve per-file history the way
    normal saves/states do: PPSSPP writes a save folder as a burst of
    several individual file PUTs a fraction of a second apart, so keeping
    every intermediate partially-merged bundle as its own history entry
    would just be noise -- only the final, fully-merged state after a save
    event is a meaningful checkpoint. The previous bundle row is deleted
    once the merged one is up, so RomM holds exactly one row per (rom, save
    folder) at a time.

    Raises `PspFolderUnresolved` if the folder can't yet be matched to a
    rom -- the file is buffered on disk and will be folded in once it is.
    """
    lock = _get_folder_lock(f"{user.id}:{info.save_folder}")
    async with lock:
        existing = _find_bundle_by_folder(user, info.save_folder)

        prior_entries: dict[str, bytes] = {}
        if existing:
            rom_id = existing.rom_id
            zip_bytes = await fs_asset_handler.read_file(existing.full_path)
            prior_entries = _load_bundle_entries(zip_bytes)
        else:
            sfo_title = None
            if info.file_name.upper() == "PARAM.SFO":
                try:
                    parsed = parse_sfo(content)
                    if isinstance(parsed.get("TITLE"), str):
                        sfo_title = str(parsed["TITLE"])
                except ValueError as exc:
                    log.warning(f"Failed to parse PARAM.SFO: {exc}")

            rom = _resolve_rom(info.save_folder, sfo_title, can_see)
            if rom is None:
                pending_dir = _pending_dir(user, info.save_folder)
                await fs_psp_pending_handler.write_file(
                    file=content,
                    path=pending_dir,
                    filename=info.file_name,
                )
                serial = _derive_serial(info.save_folder)
                log.warning(
                    f"No rom found yet for PSP save folder {hl(info.save_folder)} "
                    f"(serial {hl(serial)}) -- buffered {hl(info.file_name)}, will "
                    "merge it in once resolved (e.g. PARAM.SFO arrives)"
                )
                raise PspFolderUnresolved(info.save_folder)
            rom_id = rom.id

        # Now resolved (either an existing bundle, or fresh via this call)
        # -- fold in anything buffered earlier while this folder was
        # unresolved.
        pending_dir = _pending_dir(user, info.save_folder)
        pending: dict[str, bytes] = {}
        try:
            pending_names = await fs_psp_pending_handler.list_files(pending_dir)
        except FileNotFoundError:
            pending_names = []
        for name in pending_names:
            pending[name] = await fs_psp_pending_handler.read_file(
                f"{pending_dir}/{name}"
            )

        merged = {**prior_entries, **pending}
        merged[info.file_name] = content
        zip_bytes = _write_bundle(merged)

        rom = db_rom_handler.get_rom(rom_id)
        assert rom is not None
        saves_path = fs_asset_handler.build_saves_file_path(
            user=user,
            platform_fs_slug=rom.platform.fs_slug,
            rom_id=rom.id,
            emulator=info.emulator,
        )
        bundle_name = _bundle_base_name(info.save_folder)
        await fs_asset_handler.write_file(
            file=zip_bytes, path=saves_path, filename=bundle_name
        )

        if existing:
            db_save_handler.update_save(
                existing.id, {"file_size_bytes": len(zip_bytes)}
            )
        else:
            db_save_handler.add_save(
                Save(
                    rom_id=rom_id,
                    user_id=user.id,
                    file_name=bundle_name,
                    file_path=saves_path,
                    file_size_bytes=len(zip_bytes),
                    emulator=info.emulator,
                    slot=None,
                )
            )

        if pending_names:
            for name in pending_names:
                try:
                    await fs_psp_pending_handler.remove_file(
                        f"{pending_dir}/{name}"
                    )
                except FileNotFoundError:
                    pass


async def get_psp_file(user: User, info: PspFilePath) -> bytes | None:
    bundle = _find_bundle_by_folder(user, info.save_folder)
    if not bundle:
        return None
    zip_bytes = await fs_asset_handler.read_file(bundle.full_path)
    entries = _load_bundle_entries(zip_bytes)
    return entries.get(info.file_name)


async def delete_psp_folder(user: User, save_folder: str) -> bool:
    """Drops an entire PSP save folder's bundle -- RetroArch deletes a save
    folder file-by-file, but since the bundle is one row, the first delete
    for a folder removes it and the rest are silent no-ops (matching
    `find_bundle_by_folder` returning nothing for them)."""
    bundle = _find_bundle_by_folder(user, save_folder)
    if not bundle:
        return False

    db_save_handler.delete_save(bundle.id)
    try:
        await fs_asset_handler.remove_file(file_path=bundle.full_path)
    except FileNotFoundError:
        pass
    return True


_BUNDLE_FOLDER_PATTERN = re.compile(r"^PSP-(.+?)(?: \[.*])?\.zip$")


async def build_psp_manifest_entries(
    user: User, can_see: Callable[[Rom], bool]
) -> list[dict[str, str]]:
    """Lists every member of every PSP bundle as its own manifest entry --
    RetroArch diffs per-file, so each PARAM.SFO/ICON0.PNG/save-data file
    within a folder needs its own {path, hash}, not one entry for the whole
    bundle."""
    import hashlib

    saves = db_save_handler.get_saves(user_id=user.id)

    latest_by_folder: dict[str, Save] = {}
    for save in saves:
        match = _BUNDLE_FOLDER_PATTERN.match(save.file_name)
        if not match:
            continue
        if save.missing_from_fs or not can_see(save.rom):
            continue
        save_folder = match.group(1)
        current = latest_by_folder.get(save_folder)
        if current is None or (save.updated_at, save.id) > (
            current.updated_at,
            current.id,
        ):
            latest_by_folder[save_folder] = save

    entries: list[dict[str, str]] = []
    for save_folder, save in latest_by_folder.items():
        try:
            zip_bytes = await fs_asset_handler.read_file(save.full_path)
            members = _load_bundle_entries(zip_bytes)
        except (FileNotFoundError, zipfile.BadZipFile) as exc:
            log.warning(
                f"Failed to read PSP bundle for {hl(save_folder)}, skipping "
                f"from manifest: {exc}"
            )
            continue

        dir_name = to_retroarch_dir_name(save.emulator) if save.emulator else "PPSSPP"
        for member_name, data in members.items():
            entries.append(
                {
                    "path": f"saves/{dir_name}/PSP/SAVEDATA/{save_folder}/{member_name}",
                    "hash": hashlib.md5(data, usedforsecurity=False).hexdigest(),
                }
            )

    return entries
