import enum
from dataclasses import dataclass
from typing import Any

from sqlalchemy import inspect as sa_inspect

from config.config_manager import config_manager as cm
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.filesystem.roms_handler import RomFileKey, rom_file_key
from handler.scan_handler import persist_soundtrack_cover
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import Rom, RomFile
from utils.audio_tags import remove_persisted_cover

ROM_LEVEL_HASH_COLUMNS = ("crc_hash", "md5_hash", "sha1_hash", "ra_hash")


class HashPolicy(enum.StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"


@dataclass(frozen=True)
class RomFilesRefresh:
    files: list[RomFile]
    new_files: int
    updated_files: int
    removed_files: int
    top_level_changed: bool
    rom_updates: dict[str, Any]

    @property
    def changed(self) -> bool:
        return bool(self.new_files or self.updated_files or self.removed_files)


def loaded_rom_files(rom: Rom) -> list[RomFile]:
    """The ROM's file rows, fetched on demand when the relationship is unloaded."""
    if "files" not in sa_inspect(rom).unloaded:
        return list(rom.files)
    return db_rom_handler.rom_files_for_rom_id(rom.id)


async def refresh_rom_files(
    rom: Rom, *, hash_policy: HashPolicy = HashPolicy.INCREMENTAL
) -> RomFilesRefresh:
    """Reconcile a ROM's file rows with what is on disk.

    Args:
        rom: A persisted ROM whose folder or file exists on disk.
        hash_policy: INCREMENTAL keeps the stored hashes of unchanged files,
            FULL re-reads every file.
    Returns:
        The persisted rows and what changed, so callers can report it.
    """
    existing = loaded_rom_files(rom)
    parsed = await fs_rom_handler.get_rom_files(
        rom,
        calculate_hashes=not cm.get_config().SKIP_HASH_CALCULATION,
        existing_files=existing if hash_policy == HashPolicy.INCREMENTAL else None,
    )
    if existing and not parsed.rom_files:
        # A mount that dropped out would otherwise read as every file deleted.
        log.warning(
            f"{hl(rom.fs_name)} lists no files on disk, keeping its "
            f"{len(existing)} recorded files"
        )
        return RomFilesRefresh([], 0, 0, 0, False, {})

    existing_keys = {rom_file_key(f) for f in existing}
    reused_ids = {id(f) for f in existing}
    new_keys: set[RomFileKey] = set()
    updated_keys: set[RomFileKey] = set()
    for scanned in parsed.rom_files:
        if id(scanned) in reused_ids:
            continue
        key = rom_file_key(scanned)
        (updated_keys if key in existing_keys else new_keys).add(key)
    removed_keys = existing_keys - {rom_file_key(f) for f in parsed.rom_files}

    files = list(parsed.rom_files)
    if new_keys or updated_keys or removed_keys:
        synced = db_rom_handler.sync_rom_files(rom.id, parsed.rom_files)
        for cover_path in synced.orphaned_cover_paths:
            remove_persisted_cover(cover_path)
        for saved in synced.files:
            if rom_file_key(saved) in new_keys or rom_file_key(saved) in updated_keys:
                persist_soundtrack_cover(saved, rom)
        files = synced.files

    rom_updates: dict[str, Any] = {}
    fs_size_bytes = sum(f.file_size_bytes for f in parsed.rom_files)
    if fs_size_bytes != rom.fs_size_bytes:
        rom_updates["fs_size_bytes"] = fs_size_bytes
    if parsed.top_level_changed:
        for column in ROM_LEVEL_HASH_COLUMNS:
            value = getattr(parsed, column)
            if value != (getattr(rom, column) or ""):
                rom_updates[column] = value
    if rom.missing_from_fs:
        rom_updates["missing_from_fs"] = False
    if rom_updates:
        db_rom_handler.update_rom(rom.id, rom_updates)

    return RomFilesRefresh(
        files=files,
        new_files=len(new_keys),
        updated_files=len(updated_keys),
        removed_files=len(removed_keys),
        top_level_changed=parsed.top_level_changed,
        rom_updates=rom_updates,
    )
