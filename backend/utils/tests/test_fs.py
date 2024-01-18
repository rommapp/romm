import pytest
from unittest.mock import patch

from handler import fs_resource_handler, fs_platform_handler, fs_rom_handler
from models.platform import Platform
from config import DEFAULT_PATH_COVER_L, DEFAULT_PATH_COVER_S


@pytest.mark.vcr
def test_get_rom_cover():
    # Game: Metroid Prime (EUR).iso
    cover = fs_resource_handler.get_rom_cover(
        overwrite=False,
        platform_fs_slug="ngc",
        rom_name="Metroid Prime",
    )

    assert DEFAULT_PATH_COVER_S in cover["path_cover_s"]
    assert DEFAULT_PATH_COVER_L in cover["path_cover_l"]

    # Game: Paper Mario (USA).z64
    cover = fs_resource_handler.get_rom_cover(
        overwrite=True,
        platform_fs_slug="n64",
        rom_name="Paper Mario",
        url_cover="https://images.igdb.com/igdb/image/upload/t_thumb/co1qda.png",
    )

    assert "n64/Paper%20Mario/cover/small.png" in cover["path_cover_s"]
    assert "n64/Paper%20Mario/cover/big.png" in cover["path_cover_l"]

    # Game: Super Mario 64 (J) (Rev A)
    cover = fs_resource_handler.get_rom_cover(
        overwrite=False,
        platform_fs_slug="n64",
        rom_name="Super Mario 64",
        url_cover="https://images.igdb.com/igdb/image/upload/t_thumb/co6cl1.png",
    )

    assert "n64/Super%20Mario%2064/cover/small.png" in cover["path_cover_s"]
    assert "n64/Super%20Mario%2064/cover/big.png" in cover["path_cover_l"]

    # Game: Disney's Kim Possible: What's the Switch?.zip
    cover = fs_resource_handler.get_rom_cover(
        overwrite=False,
        platform_fs_slug="ps2",
        rom_name="Disney's Kim Possible: What's the Switch?",
        url_cover="https://images.igdb.com/igdb/image/upload/t_thumb/co6cl1.png",
    )

    assert (
        "ps2/Disney%27s%20Kim%20Possible%3A%20What%27s%20the%20Switch%3F/cover/small.png"
        in cover["path_cover_s"]
    )
    assert (
        "ps2/Disney%27s%20Kim%20Possible%3A%20What%27s%20the%20Switch%3F/cover/big.png"
        in cover["path_cover_l"]
    )

    # Game: Fake Game.xyz
    cover = fs_resource_handler.get_rom_cover(
        overwrite=False,
        platform_fs_slug="n64",
        rom_name="Fake Game",
    )

    assert DEFAULT_PATH_COVER_S in cover["path_cover_s"]
    assert DEFAULT_PATH_COVER_L in cover["path_cover_l"]


def test_get_platforms():
    platforms = fs_platform_handler.get_platforms()

    assert "n64" in platforms
    assert "psx" in platforms


def test_get_fs_structure():
    roms_structure = fs_rom_handler.get_fs_structure(fs_slug="n64")

    assert roms_structure == "n64/roms"


def test_get_roms():
    platform = Platform(name="Nintendo 64", slug="n64", fs_slug="n64")
    roms = fs_rom_handler.get_roms(platform=platform)

    assert len(roms) == 2
    assert roms[0]["file_name"] == "Paper Mario (USA).z64"
    assert not roms[0]["multi"]

    assert roms[1]["file_name"] == "Super Mario 64 (J) (Rev A)"
    assert roms[1]["multi"]


def test_rom_size():
    rom_size = fs_rom_handler.get_rom_file_size(
        roms_path=fs_rom_handler.get_fs_structure(fs_slug="n64"),
        file_name="Paper Mario (USA).z64",
        multi=False,
    )

    assert rom_size == 1024

    rom_size = fs_rom_handler.get_rom_file_size(
        roms_path=fs_rom_handler.get_fs_structure(fs_slug="n64"),
        file_name="Super Mario 64 (J) (Rev A)",
        multi=True,
        multi_files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
    )

    assert rom_size == 2048


def test_exclude_files():
    from config.config_manager import config_manager as cm

    cm.config.EXCLUDED_SINGLE_FILES = [
        "Super Mario 64 (J) (Rev A) [Part 1].z64"
    ]

    patch("utils.fs.config", cm.config)

    filtered_files = fs_rom_handler._exclude_files(
        files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
        filetype="single",
    )

    assert len(filtered_files) == 1

    cm.config.EXCLUDED_SINGLE_EXT = ["z64"]

    filtered_files = fs_rom_handler._exclude_files(
        files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
        filetype="single",
    )

    assert len(filtered_files) == 0

    cm.config.EXCLUDED_SINGLE_FILES = ["*.z64"]

    filtered_files = fs_rom_handler._exclude_files(
        files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
        filetype="single",
    )

    assert len(filtered_files) == 0

    cm.config.EXCLUDED_SINGLE_FILES = ["_.*"]

    filtered_files = fs_rom_handler._exclude_files(
        files=[
            "Links Awakening.nsp",
            "_.Links Awakening.nsp",
            "Kirby's Adventure.nsp",
            "_.Kirby's Adventure.nsp",
        ],
        filetype="single",
    )

    assert len(filtered_files) == 2
