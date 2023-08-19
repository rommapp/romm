import pytest

from ..fastapi import scan_platform, scan_rom
from exceptions.fs_exceptions import RomsNotFoundException
from models import Platform, Rom


@pytest.mark.vcr()
def test_scan_platform():
    platform = scan_platform("n64")

    assert platform.__class__ == Platform
    assert platform.slug == "n64"
    assert platform.name == "Nintendo 64"
    assert platform.igdb_id == 4

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

    assert rom.__class__ == Rom
    assert rom.file_name == "Paper Mario (USA).z64"
    assert rom.r_name == "Paper Mario"
    assert rom.r_igdb_id == 3340
    assert rom.file_size == 1.0
    assert rom.file_size_units == "KB"
    assert rom.files == ["Paper Mario (USA).z64"]
    assert rom.tags == []
    assert not rom.multi
