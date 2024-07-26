import pytest
from exceptions.fs_exceptions import RomsNotFoundException
from handler.scan_handler import ScanType, scan_platform, scan_rom
from models.platform import Platform
from models.rom import Rom
from utils.context import initialize_context


@pytest.mark.vcr
def test_scan_platform():
    platform = scan_platform("n64", ["n64"])

    assert type(platform) is Platform
    assert platform.fs_slug == "n64"
    assert platform.slug == "n64"
    assert platform.name == "Nintendo 64"
    assert platform.igdb_id == 4

    try:
        platform = scan_platform("", [])
    except RomsNotFoundException as e:
        assert "Roms not found for platform" in str(e)


@pytest.mark.vcr
async def test_scan_rom():
    platform = Platform(fs_slug="n64", igdb_id=4)

    async with initialize_context():
        files = [
            {
                "file_name": "Paper Mario (USA).z64",
                "crc_hash": "9d0d1c6e",
                "md5_hash": "f1b7f9e4f4d0e0b7b9faa1b1f2f8e4e9",
                "sha1_hash": "c3c7f9f3d1d0e0b7b9faa1b1f2f8e4e9",
            }
        ]

        rom = await scan_rom(
            platform,
            {"file_name": "Paper Mario (USA).z64", "multi": False, "files": files},
            ScanType.QUICK,
        )

    assert type(rom) is Rom
    assert rom.file_name == "Paper Mario (USA).z64"
    assert rom.name == "Paper Mario"
    assert rom.igdb_id == 3340
    assert rom.file_size_bytes == 1024
    assert rom.files == files
    assert rom.tags == []
    assert not rom.multi
