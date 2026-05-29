import pytest

from handler.database import db_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User


@pytest.fixture
def multi_file_rom(admin_user: User, platform: Platform) -> Rom:
    """A folder-based ROM with two top-level files (so has_simple_single_file is False)."""
    rom = Rom(
        platform_id=platform.id,
        name="multi_rom",
        slug="multi_rom_slug",
        fs_name="multi_rom",
        fs_name_no_tags="multi_rom",
        fs_name_no_ext="multi_rom",
        fs_extension="",
        fs_path=f"{platform.slug}/roms",
    )
    rom = db_rom_handler.add_rom(rom)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    file_path = f"{platform.slug}/roms/multi_rom"
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="game.bin",
            file_path=file_path,
            file_size_bytes=10,
            category=RomFileCategory.GAME,
        )
    )
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="readme.txt",
            file_path=file_path,
            file_size_bytes=5,
            category=RomFileCategory.GAME,
        )
    )
    return db_rom_handler.get_rom(rom.id)
