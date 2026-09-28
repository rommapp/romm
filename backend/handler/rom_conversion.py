import asyncio

from exceptions.fs_exceptions import RomAlreadyExistsException
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import Rom

_STAGE_PREFIX = ".romm_tmp_"

# Uploading several files fires a request per file, each promoting the same ROM.
_promotion_lock = asyncio.Lock()


async def promote_single_file_to_folder(rom: Rom) -> Rom:
    """Promote a simple single-file ROM to a folder ROM in place, keeping rom.id
    and every relation. Idempotent; raises RomAlreadyExistsException on a
    folder-name collision.
    """
    async with _promotion_lock:
        return await _promote(db_rom_handler.get_rom(rom.id) or rom)


async def _promote(rom: Rom) -> Rom:
    if not rom.has_simple_single_file:
        return rom

    folder = rom.fs_name_no_ext
    fs_path = rom.fs_path
    fs_name = rom.fs_name
    origin = f"{fs_path}/{fs_name}"
    dest_dir = f"{fs_path}/{folder}"
    final = f"{dest_dir}/{fs_name}"
    staged = f"{fs_path}/{_STAGE_PREFIX}{fs_name}"
    extensionless = folder == fs_name

    # Extensionless dest_dir is the file's own path; only a directory collides.
    dest_path = fs_rom_handler.validate_path(dest_dir)
    collision = dest_path.is_dir() if extensionless else dest_path.exists()
    if collision:
        raise RomAlreadyExistsException(folder)

    # A promotion racing this one from another worker can win the move and own
    # the folder, so undo only what this call did. Removal is recursive, and a
    # folder with anything left in it holds someone else's ROM.
    moved = False

    async def _drop_dir() -> None:
        path = fs_rom_handler.validate_path(dest_dir)
        if path.is_dir() and not any(path.iterdir()):
            await fs_rom_handler.remove_directory(dest_dir)

    async def _restore() -> None:
        """Return the lone file to its original path and drop the new folder."""
        src = next(
            (
                p
                for p in (final, staged)
                if moved and fs_rom_handler.validate_path(p).exists()
            ),
            None,
        )
        if src is not None and extensionless:
            if src != staged:
                await fs_rom_handler.move_file_or_folder(src, staged)
            await _drop_dir()
            await fs_rom_handler.move_file_or_folder(staged, origin)
        elif src is not None:
            await fs_rom_handler.move_file_or_folder(src, origin)
            await _drop_dir()
        else:
            await _drop_dir()

    try:
        if extensionless:
            await fs_rom_handler.move_file_or_folder(origin, staged)
            moved = True
            await fs_rom_handler.make_directory(dest_dir)
            await fs_rom_handler.move_file_or_folder(staged, final)
        else:
            await fs_rom_handler.make_directory(dest_dir)
            await fs_rom_handler.move_file_or_folder(origin, final)
            moved = True
        db_rom_handler.convert_rom_to_folder(rom.id, folder, dest_dir)
    except Exception:
        try:
            await _restore()
        except Exception:
            log.error(f"Failed to roll back folder conversion for ROM {rom.id}")
        raise

    refetched = db_rom_handler.get_rom(rom.id)
    if refetched is None:
        return rom

    log.info(
        f"Converted {hl(rom.name or 'ROM', color=BLUE)} [{hl(fs_name)}] "
        f"to folder ROM [{hl(folder)}]"
    )
    return refetched
