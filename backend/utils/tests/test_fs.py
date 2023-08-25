import pytest

from ..fs import (
    get_cover,
    get_platforms,
    get_roms_structure,
    get_roms,
    get_rom_size,
    # get_rom_files,  # TODO: write test
    # rename_rom,  # TODO: write test
    # remove_rom,  # TODO: write test
)

from config import (
    DEFAULT_PATH_COVER_L,
    DEFAULT_PATH_COVER_S,
)


@pytest.mark.vcr
def test_get_cover():
    # Game: Paper Mario (USA).z64
    cover = get_cover(
        overwrite=False,
        p_slug="n64",
        r_name="Paper Mario",
    )

    assert "n64/Paper Mario/cover/small.png" in cover["path_cover_s"]
    assert "n64/Paper Mario/cover/big.png" in cover["path_cover_l"]
    assert cover["has_cover"] == 1

    # Game: Paper Mario (USA).z64
    cover = get_cover(
        overwrite=True,
        p_slug="n64",
        r_name="Paper Mario",
        url_cover="https://images.igdb.com/igdb/image/upload/t_thumb/co1qda.png",
    )

    assert "n64/Paper Mario/cover/small.png" in cover["path_cover_s"]
    assert "n64/Paper Mario/cover/big.png" in cover["path_cover_l"]
    assert cover["has_cover"] == 1

    # Game: Super Mario 64 (J) (Rev A)
    cover = get_cover(
        overwrite=False,
        p_slug="n64",
        r_name="Super Mario 64",
        url_cover="https://images.igdb.com/igdb/image/upload/t_thumb/co6cl1.png",
    )

    assert "n64/Super Mario 64/cover/small.png" in cover["path_cover_s"]
    assert "n64/Super Mario 64/cover/big.png" in cover["path_cover_l"]
    assert cover["has_cover"] == 1

    # Game: Fake Game.xyz
    cover = get_cover(
        overwrite=False,
        p_slug="n64",
        r_name="Fake Game",
    )

    assert DEFAULT_PATH_COVER_S in cover["path_cover_s"]
    assert DEFAULT_PATH_COVER_L in cover["path_cover_l"]
    assert cover["has_cover"] == 0


def test_get_platforms():
    platforms = get_platforms()

    assert "n64" in platforms
    assert "psx" in platforms


def test_get_roms_structure():
    roms_structure = get_roms_structure(p_slug="n64")

    assert roms_structure == "n64/roms"


def test_get_roms():
    roms = get_roms(p_slug="n64")

    assert len(roms) == 2
    assert roms[0]["file_name"] == "Paper Mario (USA).z64"
    assert not roms[0]["multi"]

    assert roms[1]["file_name"] == "Super Mario 64 (J) (Rev A)"
    assert roms[1]["multi"]


def test_rom_size():
    rom_size = get_rom_size(
        roms_path=get_roms_structure(p_slug="n64"),
        file_name="Paper Mario (USA).z64",
        multi=False,
    )

    assert rom_size == (1.0, "KB")

    rom_size = get_rom_size(
        roms_path=get_roms_structure(p_slug="n64"),
        file_name="Super Mario 64 (J) (Rev A)",
        multi=True,
        multi_files=[
            "Super Mario 64 (J) (Rev A) [Part 1].z64",
            "Super Mario 64 (J) (Rev A) [Part 2].z64",
        ],
    )

    assert rom_size == (2.0, "KB")
