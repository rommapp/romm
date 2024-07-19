import os
from pathlib import Path

import pytest
from handler.filesystem import fs_platform_handler, fs_resource_handler, fs_rom_handler
from models.platform import Platform


@pytest.mark.vcr
def test_get_rom_cover():
    path_cover_s, path_cover_l = fs_resource_handler.get_cover(
        overwrite=False, entity=None, url_cover=""
    )

    assert "" in path_cover_s
    assert "" in path_cover_l


def test_get_platforms():
    platforms = fs_platform_handler.get_platforms()

    assert "n64" in platforms
    assert "psx" in platforms


def test_get_roms_fs_structure():
    roms_structure = fs_rom_handler.get_roms_fs_structure(fs_slug="n64")

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
        roms_path=fs_rom_handler.get_roms_fs_structure(fs_slug="n64"),
        file_name="Paper Mario (USA).z64",
        multi=False,
    )

    assert rom_size == 1024

    rom_size = fs_rom_handler.get_rom_file_size(
        roms_path=fs_rom_handler.get_roms_fs_structure(fs_slug="n64"),
        file_name="Super Mario 64 (J) (Rev A)",
        multi=True,
        multi_files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
    )

    assert rom_size == 2048


def test_exclude_files():
    from config.config_manager import ConfigManager

    empty_config_file = os.path.join(
        Path(__file__).resolve().parent.parent.parent.parent,
        "config/tests/fixtures/config/empty_config.yml",
    )

    ConfigManager(empty_config_file)
    from config.config_manager import config_manager as cm

    cm.add_exclusion("EXCLUDED_SINGLE_FILES", "Super Mario 64 (J) (Rev A) [Part 1].z64")

    filtered_files = fs_rom_handler._exclude_files(
        files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
        filetype="single",
    )

    assert len(filtered_files) == 1

    cm.add_exclusion("EXCLUDED_SINGLE_EXT", "z64")

    filtered_files = fs_rom_handler._exclude_files(
        files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
        filetype="single",
    )

    assert len(filtered_files) == 0

    cm.add_exclusion("EXCLUDED_SINGLE_FILES", "*.z64")

    filtered_files = fs_rom_handler._exclude_files(
        files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
        filetype="single",
    )

    assert len(filtered_files) == 0

    cm.add_exclusion("EXCLUDED_SINGLE_FILES", "_.*")

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

    with open(empty_config_file, "w") as file:
        file.write("")


def test_parse_tags():
    file_name = "Super Mario Bros. (World).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["World"], "", [], [])

    file_name = "Super Mario Bros. (W) (Rev A).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["World"], "A", [], [])

    file_name = "Super Mario Bros. (USA) (Rev A) (Beta).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["USA"], "A", [], ["Beta"])

    file_name = "Super Mario Bros. (U) (Beta).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["USA"], "", [], ["Beta"])

    file_name = "Super Mario Bros. (CH) [!].nes"
    assert fs_rom_handler.parse_tags(file_name) == (["China"], "", [], ["!"])

    file_name = "Super Mario Bros. (reg-T) (rev-1.2).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["Taiwan"], "1.2", [], [])

    file_name = "Super Mario Bros. (Reg S) (Rev A).nes"
    assert fs_rom_handler.parse_tags(file_name) == (["Spain"], "A", [], [])

    file_name = "Super Metroid (Japan, USA) (En,Ja).zip"
    assert fs_rom_handler.parse_tags(file_name) == (
        ["Japan", "USA"],
        "",
        ["English", "Japanese"],
        [],
    )


def test_get_file_name_with_no_tags():
    file_name = "Super Mario Bros. (World).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (W) (Rev A).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (USA) (Rev A) (Beta).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (U) (Beta).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (U) [!].nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (reg-T) (rev-1.2).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "Super Mario Bros. (Reg S) (Rev A).nes"
    assert fs_rom_handler.get_file_name_with_no_tags(file_name) == "Super Mario Bros."

    file_name = "007 - Agent Under Fire.nkit.iso"
    assert (
        fs_rom_handler.get_file_name_with_no_tags(file_name) == "007 - Agent Under Fire"
    )

    file_name = "Jimmy Houston's Bass Tournament U.S.A..zip"
    assert (
        fs_rom_handler.get_file_name_with_no_tags(file_name)
        == "Jimmy Houston's Bass Tournament U.S.A."
    )

    # This is expected behavior, since the regex is aggressive
    file_name = "Battle Stadium D.O.N.zip"
    assert (
        fs_rom_handler.get_file_name_with_no_tags(file_name) == "Battle Stadium D.O.N"
    )


def test_get_file_name_with_no_extension():
    file_name = "Super Mario Bros. (World).nes"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "Super Mario Bros. (World)"
    )

    file_name = "Super Mario Bros. (W) (Rev A).nes"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "Super Mario Bros. (W) (Rev A)"
    )

    file_name = "Super Mario Bros. (USA) (Rev A) (Beta).nes"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "Super Mario Bros. (USA) (Rev A) (Beta)"
    )

    file_name = "Super Mario Bros. (U) (Beta).nes"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "Super Mario Bros. (U) (Beta)"
    )

    file_name = "Super Mario Bros. (U) [!].nes"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "Super Mario Bros. (U) [!]"
    )

    file_name = "Super Mario Bros. (reg-T) (rev-1.2).nes"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "Super Mario Bros. (reg-T) (rev-1.2)"
    )

    file_name = "Super Mario Bros. (Reg S) (Rev A).nes"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "Super Mario Bros. (Reg S) (Rev A)"
    )

    file_name = "007 - Agent Under Fire.nkit.iso"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "007 - Agent Under Fire"
    )

    file_name = "Jimmy Houston's Bass Tournament U.S.A..zip"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "Jimmy Houston's Bass Tournament U.S.A."
    )

    file_name = "Battle Stadium D.O.N.zip"
    assert (
        fs_rom_handler.get_file_name_with_no_extension(file_name)
        == "Battle Stadium D.O.N"
    )


def test_get_file_extension():
    assert fs_rom_handler.parse_file_extension("Super Mario Bros. (World).nes") == "nes"
    assert (
        fs_rom_handler.parse_file_extension("007 - Agent Under Fire.nkit.iso")
        == "nkit.iso"
    )
