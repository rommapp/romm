import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from sqlalchemy import inspect as sa_inspect

from config.config_manager import config_manager as cm
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.filesystem.roms_handler import RomFileKey, rom_file_key
from handler.redis_handler import async_cache
from handler.scan_handler import persist_soundtrack_cover
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import Rom, RomFile, RomIdentity
from utils.audio_tags import remove_persisted_cover

ROM_LEVEL_HASH_COLUMNS = ("crc_hash", "md5_hash", "sha1_hash", "ra_hash")

# A refresh lists the folder and then deletes every row the listing missed, so
# two of them running for the same rom (parallel uploads into one folder) would
# let the slower listing drop what the faster one just registered. The lock
# lives in Redis because the uploads may land on different gunicorn workers,
# and is a plain SET NX so it also works without Lua scripting.
REFRESH_LOCK_TIMEOUT_SECONDS = 600
REFRESH_LOCK_POLL_SECONDS = 0.1


@asynccontextmanager
async def _refresh_lock(rom_id: int) -> AsyncIterator[None]:
    key = f"rom_files_refresh:{rom_id}"
    token = uuid4().hex
    for _ in range(int(REFRESH_LOCK_TIMEOUT_SECONDS / REFRESH_LOCK_POLL_SECONDS)):
        if await async_cache.set(key, token, nx=True, ex=REFRESH_LOCK_TIMEOUT_SECONDS):
            break
        await asyncio.sleep(REFRESH_LOCK_POLL_SECONDS)
    else:
        raise TimeoutError(f"Timed out waiting to refresh the files of ROM {rom_id}")
    try:
        yield
    finally:
        # Only the owner releases; an expired lock may belong to someone else.
        held = await async_cache.get(key)
        if held in (token, token.encode()):
            await async_cache.delete(key)


@dataclass(frozen=True)
class RomFilesRefresh:
    new_files: int
    updated_files: int
    removed_files: int

    @property
    def changed(self) -> bool:
        return bool(self.new_files or self.updated_files or self.removed_files)


def loaded_rom_files(rom: Rom) -> list[RomFile]:
    """The ROM's file rows, fetched on demand when the relationship is unloaded."""
    if "files" not in sa_inspect(rom).unloaded:
        return list(rom.files)
    return db_rom_handler.rom_files_for_rom_id(rom.id)


async def refresh_rom_files(rom: Rom) -> RomFilesRefresh:
    """Reconcile a ROM's file rows with what is on disk, keeping the stored
    hashes of files whose size and mtime are unchanged.

    Args:
        rom: A persisted ROM whose folder or file exists on disk.
    Returns:
        What changed, so callers can report it.
    """
    async with _refresh_lock(rom.id):
        return await _refresh(rom)


async def _refresh(rom: Rom) -> RomFilesRefresh:
    existing = loaded_rom_files(rom)
    cnfg = cm.get_config()
    calculate_hashes = not cnfg.SKIP_HASH_CALCULATION
    parsed = await fs_rom_handler.get_rom_files(
        rom,
        calculate_hashes=calculate_hashes,
        extract_title_ids=not cnfg.SKIP_TITLE_ID_EXTRACTION,
        existing_files=existing,
    )
    if existing and not parsed.rom_files:
        # A mount that dropped out would otherwise read as every file deleted.
        log.warning(
            f"{hl(rom.fs_name)} lists no files on disk, keeping its "
            f"{len(existing)} recorded files"
        )
        return RomFilesRefresh(0, 0, 0)

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

    if new_keys or updated_keys or removed_keys:
        synced = db_rom_handler.sync_rom_files(rom.id, parsed.rom_files)
        for cover_path in synced.orphaned_cover_paths:
            remove_persisted_cover(cover_path)
        for saved in synced.files:
            if rom_file_key(saved) in new_keys or rom_file_key(saved) in updated_keys:
                persist_soundtrack_cover(saved, rom)

    rom_updates: dict[str, Any] = {}
    fs_size_bytes = sum(f.file_size_bytes for f in parsed.rom_files)
    if fs_size_bytes != rom.fs_size_bytes:
        rom_updates["fs_size_bytes"] = fs_size_bytes
    # With hashing disabled the listing carries no digests, so the stored
    # hashes outlive it rather than being blanked.
    if parsed.top_level_changed and calculate_hashes:
        for column in ROM_LEVEL_HASH_COLUMNS:
            value = getattr(parsed, column)
            if value != (getattr(rom, column) or ""):
                rom_updates[column] = value
    # Only written when the parse actually read an id, so a refresh that read
    # none (extraction disabled, or every file unchanged) leaves the stored
    # triple alone rather than blanking it.
    if parsed.identity.title_id and parsed.identity != RomIdentity.from_rom(rom):
        rom_updates.update(parsed.identity.as_rom_attrs())
    if rom.missing_from_fs:
        rom_updates["missing_from_fs"] = False
    if rom_updates:
        db_rom_handler.update_rom(rom.id, rom_updates)

    return RomFilesRefresh(
        new_files=len(new_keys),
        updated_files=len(updated_keys),
        removed_files=len(removed_keys),
    )
