from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from handler.database import db_rom_handler
from handler.filesystem import fs_resource_handler
from handler.filesystem.roms_handler import NativeIconResult
from handler.scan_handler import persist_native_icon
from models.rom import Rom, RomFile


async def test_no_fresh_result_keeps_the_stored_icon(mocker):
    rom = Rom(id=1, path_icon="roms/1/1/icon.png")
    store = mocker.patch.object(fs_resource_handler, "store_native_icon", AsyncMock())
    update = mocker.patch.object(db_rom_handler, "update_rom", Mock())

    await persist_native_icon(rom, None)

    store.assert_not_awaited()
    update.assert_not_called()
    assert rom.path_icon == "roms/1/1/icon.png"


async def test_an_authoritative_no_icon_result_clears_the_stored_icon(mocker):
    rom = Rom(id=1, path_icon="roms/1/1/icon.png")
    remove = mocker.patch.object(fs_resource_handler, "remove_native_icon", AsyncMock())
    update = mocker.patch.object(db_rom_handler, "update_rom", Mock())

    await persist_native_icon(rom, NativeIconResult(None))

    remove.assert_awaited_once_with(rom)
    update.assert_called_once_with(rom.id, {"path_icon": None})
    assert rom.path_icon is None


async def test_a_failed_store_keeps_the_stored_icon(mocker):
    rom = Rom(id=1, path_icon="roms/1/1/icon.png")
    store = mocker.patch.object(
        fs_resource_handler, "store_native_icon", AsyncMock(return_value=None)
    )
    update = mocker.patch.object(db_rom_handler, "update_rom", Mock())

    await persist_native_icon(rom, NativeIconResult(b"invalid"))

    store.assert_awaited_once_with(rom, b"invalid")
    update.assert_not_called()
    assert rom.path_icon == "roms/1/1/icon.png"


async def test_a_storage_error_marks_the_primary_file_for_retry(mocker):
    source = RomFile(id=7, converto_read_at=datetime.now(timezone.utc))
    rom = Rom(id=1, path_icon="roms/1/1/icon.png")
    mocker.patch.object(
        fs_resource_handler,
        "store_native_icon",
        AsyncMock(side_effect=OSError("disk full")),
    )
    update = mocker.patch.object(db_rom_handler, "update_rom_file", Mock())

    await persist_native_icon(rom, NativeIconResult(b"png", source))

    assert source.converto_read_at is None
    update.assert_called_once_with(source.id, {"converto_read_at": None})
    assert rom.path_icon == "roms/1/1/icon.png"


async def test_fresh_icon_bytes_update_the_path_and_database(mocker):
    rom = Rom(id=1)
    path = "roms/1/1/icon.png"
    mocker.patch.object(
        fs_resource_handler, "store_native_icon", AsyncMock(return_value=path)
    )
    update = mocker.patch.object(db_rom_handler, "update_rom", Mock())

    await persist_native_icon(rom, NativeIconResult(b"png"))

    update.assert_called_once_with(rom.id, {"path_icon": path})
    assert rom.path_icon == path
