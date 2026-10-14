from pathlib import Path

import pytest

from handler.database import db_device_handler, db_rom_handler
from handler.filesystem import fs_asset_handler
from models.device import Device
from models.rom import Rom, RomFile
from models.user import User


@pytest.fixture(autouse=True)
def _assets_dir(tmp_path, monkeypatch) -> Path:
    base = Path(tmp_path).resolve()
    monkeypatch.setattr(fs_asset_handler, "base_path", base)
    return base


@pytest.fixture
def hashed_file(rom: Rom) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="game.sfc",
            file_path=rom.fs_path,
            file_size_bytes=1024,
            sha1_hash="a" * 40,
        )
    )


@pytest.fixture
def device(admin_user: User) -> Device:
    return db_device_handler.add_device(
        Device(id="device-1", user_id=admin_user.id, name="Odin")
    )
