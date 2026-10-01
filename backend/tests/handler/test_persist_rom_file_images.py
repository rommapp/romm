from pathlib import Path

import pytest

import handler.scan_handler as scan_handler
from adapters.services.rom_converto import RomConvertoImages
from handler.filesystem import fs_resource_handler
from handler.scan_handler import persist_rom_file_images
from models.rom import Rom, RomFile


@pytest.fixture
def resources_dir(tmp_path: Path, mocker):
    mocker.patch.object(fs_resource_handler, "base_path", tmp_path)
    mocker.patch("config.RESOURCES_BASE_PATH", str(tmp_path))
    return tmp_path


def _rom() -> Rom:
    rom = Rom(platform_id=7)
    rom.id = 3
    return rom


def _rom_file(**overrides) -> RomFile:
    rom_file = RomFile(
        rom_id=3,
        file_name="game.iso",
        file_path="psx/roms/game",
        **overrides,
    )
    rom_file.id = 21
    return rom_file


@pytest.mark.asyncio
async def test_persists_each_present_image_and_records_all_paths(resources_dir, mocker):
    db = mocker.patch.object(scan_handler, "db_rom_handler")
    rom_file = _rom_file()
    images = RomConvertoImages(
        icon=b"\x89PNG\r\n\x1a\nicon",
        banner=b"\x89PNG\r\n\x1a\nbanner",
        background=b"\x89PNG\r\n\x1a\nbackground",
    )

    await persist_rom_file_images(rom_file, images, _rom())

    expected = {
        "icon_path": "roms/7/3/icons/21.png",
        "banner_path": "roms/7/3/banners/21.png",
        "background_path": "roms/7/3/backgrounds/21.png",
    }
    for kind, column in (
        ("icon", "icon_path"),
        ("banner", "banner_path"),
        ("background", "background_path"),
    ):
        path = resources_dir / expected[column]
        assert path.read_bytes() == getattr(images, kind)
    db.update_rom_file.assert_called_once_with(21, expected)


@pytest.mark.asyncio
async def test_lost_image_is_removed_and_its_path_cleared(resources_dir, mocker):
    db = mocker.patch.object(scan_handler, "db_rom_handler")
    relative_path = "roms/7/3/icons/21.png"
    existing = resources_dir / relative_path
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"old image")
    rom_file = _rom_file(icon_path=relative_path)

    await persist_rom_file_images(rom_file, RomConvertoImages(), _rom())

    assert not existing.exists()
    db.update_rom_file.assert_called_once_with(21, {"icon_path": None})


@pytest.mark.asyncio
async def test_failed_image_unlink_keeps_its_path(resources_dir, mocker):
    remove = mocker.patch.object(
        scan_handler, "remove_persisted_cover", return_value=False
    )
    db = mocker.patch.object(scan_handler, "db_rom_handler")
    rom_file = _rom_file(icon_path="roms/7/3/icons/21.png")

    await persist_rom_file_images(rom_file, RomConvertoImages(), _rom())

    remove.assert_called_once_with("roms/7/3/icons/21.png")
    db.update_rom_file.assert_not_called()


@pytest.mark.asyncio
async def test_unchanged_image_paths_skip_the_database_update(resources_dir, mocker):
    db = mocker.patch.object(scan_handler, "db_rom_handler")
    icon_path = "roms/7/3/icons/21.png"
    banner_path = "roms/7/3/banners/21.png"
    background_path = "roms/7/3/backgrounds/21.png"
    rom_file = _rom_file(
        icon_path=icon_path,
        banner_path=banner_path,
        background_path=background_path,
    )

    await persist_rom_file_images(
        rom_file,
        RomConvertoImages(
            icon=b"\x89PNG\r\n\x1a\nicon",
            banner=b"\x89PNG\r\n\x1a\nbanner",
            background=b"\x89PNG\r\n\x1a\nbackground",
        ),
        _rom(),
    )

    assert (resources_dir / icon_path).read_bytes() == b"\x89PNG\r\n\x1a\nicon"
    assert (resources_dir / banner_path).read_bytes() == b"\x89PNG\r\n\x1a\nbanner"
    assert (
        resources_dir / background_path
    ).read_bytes() == b"\x89PNG\r\n\x1a\nbackground"
    db.update_rom_file.assert_not_called()


@pytest.mark.asyncio
async def test_image_write_error_skips_only_that_path(resources_dir, mocker):
    db = mocker.patch.object(scan_handler, "db_rom_handler")
    mocker.patch.object(
        fs_resource_handler,
        "write_file",
        side_effect=[OSError("disk full"), None],
    )
    rom_file = _rom_file()

    await persist_rom_file_images(
        rom_file, RomConvertoImages(icon=b"icon", banner=b"banner"), _rom()
    )

    db.update_rom_file.assert_called_once_with(
        21, {"banner_path": "roms/7/3/banners/21.png"}
    )
