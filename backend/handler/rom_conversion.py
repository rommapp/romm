from exceptions.fs_exceptions import RomAlreadyExistsException
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import Rom

_STAGE_PREFIX = ".romm_tmp_"


async def promote_single_file_to_folder(rom: Rom) -> Rom:
    """Promote a simple single-file ROM to a folder ROM in place, keeping rom.id
    and every relation. Idempotent; raises RomAlreadyExistsException on a
    folder-name collision.
    """
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

    if not extensionless and fs_rom_handler.validate_path(dest_dir).exists():
        raise RomAlreadyExistsException(folder)

    if extensionless:
        await fs_rom_handler.move_file_or_folder(origin, staged)
        await fs_rom_handler.make_directory(dest_dir)
        await fs_rom_handler.move_file_or_folder(staged, final)
    else:
        await fs_rom_handler.make_directory(dest_dir)
        await fs_rom_handler.move_file_or_folder(origin, final)

    try:
        db_rom_handler.convert_rom_to_folder(rom.id, folder, dest_dir)
    except Exception:
        try:
            if extensionless:
                await fs_rom_handler.move_file_or_folder(final, staged)
                await fs_rom_handler.remove_directory(dest_dir)
                await fs_rom_handler.move_file_or_folder(staged, origin)
            else:
                await fs_rom_handler.move_file_or_folder(final, origin)
                await fs_rom_handler.remove_directory(dest_dir)
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
