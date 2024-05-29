import pytest

from handler.scan_handler import scan_platform, scan_rom, ScanType
from exceptions.fs_exceptions import RomsNotFoundException
from models.platform import Platform
from models.rom import Rom


@pytest.mark.vcr
def test_scan_platform():
    platform = scan_platform("n64", "n64")

    assert platform.__class__ == Platform
    assert platform.fs_slug == "n64"
    assert platform.slug == "n64"
    assert platform.name == "Nintendo 64"
    assert platform.igdb_id == 4

    try:
        platform = scan_platform("", "")
    except RomsNotFoundException as e:
        assert "Roms not found for platform" in str(e)


@pytest.mark.vcr
async def test_scan_rom():
    platform = Platform(fs_slug="n64", igdb_id=4)
    files = [{
        "file_name": "Paper Mario (USA).z64",
        "crc_hash": "9d0d1c6e",
        "md5_hash": "f1b7f9e4f4d0e0b7b9faa1b1f2f8e4e9",
        "sha1_hash": "c3c7f9f3d1d0e0b7b9faa1b1f2f8e4e9",
    }]

    rom = await scan_rom(
        platform,
        {
            "file_name": "Paper Mario (USA).z64",
            "multi": False,
            "files": files,
        },
        ScanType.QUICK,
    )

    assert rom.__class__ == Rom
    assert rom.file_name == "Paper Mario (USA).z64"
    assert rom.name == "Paper Mario"
    assert rom.igdb_id == 3340
    assert rom.file_size_bytes == 1024
    assert rom.files == files
    assert rom.tags == []
    assert not rom.multi
