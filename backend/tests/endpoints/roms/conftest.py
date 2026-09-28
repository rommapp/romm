from pathlib import Path

import pytest

from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User


@pytest.fixture
def real_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point fs_rom_handler at a real temp library so file moves and listings
    actually happen."""
    lib = tmp_path / "library"
    lib.mkdir()
    monkeypatch.setattr(fs_rom_handler, "base_path", lib.resolve())
    return lib


@pytest.fixture
def game_folder_on_disk(real_library: Path, game_folder_rom: Rom) -> Path:
    """The folder ROM's directory in the real library, with every file row
    written to disk so a refresh keeps them."""
    for rom_file in game_folder_rom.files:
        path = real_library / rom_file.full_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\0" * rom_file.file_size_bytes)
    return real_library / game_folder_rom.full_path


@pytest.fixture
def game_folder_rom(admin_user: User, platform: Platform) -> Rom:
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
    refreshed = db_rom_handler.get_rom(rom.id)
    assert refreshed is not None
    return refreshed
