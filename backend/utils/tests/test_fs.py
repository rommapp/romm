import pytest

from ..fs import (
    get_rom_cover,
    get_platforms,
    get_fs_structure,
    get_roms,
    get_rom_file_size,
    # get_rom_screenshots # TODO: write test
    # store_default_resources # TODO: write test
    # get_rom_files,  # TODO: write test
    # rename_file,  # TODO: write test
    # remove_file,  # TODO: write test
    # build_upload_file_path, # TODO: write test
    # build_artwork_path, # TODO: write test
    # build_avatar_path, # TODO: write test
)

from config import (
    DEFAULT_PATH_COVER_L,
    DEFAULT_PATH_COVER_S,
)


@pytest.mark.vcr
def test_get_rom_cover():
    # Game: Metroid Prime (EUR).iso
    cover = get_rom_cover(
        overwrite=False,
        fs_slug="ngc",
        rom_name="Metroid Prime",
    )

    assert DEFAULT_PATH_COVER_S in cover["path_cover_s"]
    assert DEFAULT_PATH_COVER_L in cover["path_cover_l"]

    # Game: Paper Mario (USA).z64
    cover = get_rom_cover(
        overwrite=True,
        fs_slug="n64",
        rom_name="Paper Mario",
        url_cover="https://images.igdb.com/igdb/image/upload/t_thumb/co1qda.png",
    )

    assert "n64/Paper%20Mario/cover/small.png" in cover["path_cover_s"]
    assert "n64/Paper%20Mario/cover/big.png" in cover["path_cover_l"]

    # Game: Super Mario 64 (J) (Rev A)
    cover = get_rom_cover(
        overwrite=False,
        fs_slug="n64",
        rom_name="Super Mario 64",
        url_cover="https://images.igdb.com/igdb/image/upload/t_thumb/co6cl1.png",
    )

    assert "n64/Super%20Mario%2064/cover/small.png" in cover["path_cover_s"]
    assert "n64/Super%20Mario%2064/cover/big.png" in cover["path_cover_l"]

    # Game: Disney's Kim Possible: What's the Switch?.zip
    cover = get_rom_cover(
        overwrite=False,
        fs_slug="ps2",
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
    cover = get_rom_cover(
        overwrite=False,
        fs_slug="n64",
        rom_name="Fake Game",
    )

    assert DEFAULT_PATH_COVER_S in cover["path_cover_s"]
    assert DEFAULT_PATH_COVER_L in cover["path_cover_l"]


def test_get_platforms():
    platforms = get_platforms()

    assert "n64" in platforms
    assert "psx" in platforms


def test_get_fs_structure():
    roms_structure = get_fs_structure(fs_slug="n64")

    assert roms_structure == "n64/roms"


def test_get_roms():
    roms = get_roms(fs_slug="n64")

    assert len(roms) == 2
    assert roms[0]["file_name"] == "Paper Mario (USA).z64"
    assert not roms[0]["multi"]

    assert roms[1]["file_name"] == "Super Mario 64 (J) (Rev A)"
    assert roms[1]["multi"]


def test_rom_size():
    rom_size = get_rom_file_size(
        roms_path=get_fs_structure(fs_slug="n64"),
        file_name="Paper Mario (USA).z64",
        multi=False,
    )

    assert rom_size == (1.0, "KB")

    rom_size = get_rom_file_size(
        roms_path=get_fs_structure(fs_slug="n64"),
        file_name="Super Mario 64 (J) (Rev A)",
        multi=True,
        multi_files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
    )

    assert rom_size == (2.0, "KB")
