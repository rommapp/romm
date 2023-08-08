import pytest

from utils.fastapi import scan_platform, scan_rom
from utils.exceptions import RomsNotFoundException
from models.platform import Platform
from models.rom import Rom


@pytest.mark.vcr()
def test_scan_platform():
    platform = scan_platform("n64")

    assert platform.__class__ == Platform # type: ignore
    assert platform.slug == "n64" # type: ignore
    assert platform.name == "Nintendo 64" # type: ignore
    assert platform.igdb_id == 4 # type: ignore

    try:
        platform = scan_platform("")
    except RomsNotFoundException as e:
        assert "Roms not found for platform" in str(e)


@pytest.mark.vcr()
def test_scan_rom():
    platform = Platform(slug="n64", igdb_id=4)
    rom = scan_rom(
        platform,
        {
            "file_name": "Paper Mario (USA).z64",
            "multi": False,
            "files": ["Paper Mario (USA).z64"],
        },
    )

    assert rom.__class__ == Rom # type: ignore
    assert rom.file_name == "Paper Mario (USA).z64" # type: ignore
    assert rom.r_name == "Paper Mario" # type: ignore
    assert rom.r_igdb_id == 3340 # type: ignore
    assert rom.file_size == 1.0 # type: ignore
    assert rom.file_size_units == "KB" # type: ignore
    assert rom.files == ["Paper Mario (USA).z64"] # type: ignore
    assert rom.tags == [] # type: ignore
    assert not rom.multi # type: ignore
