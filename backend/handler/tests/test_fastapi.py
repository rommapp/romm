import pytest
from handler.scan_handler import ScanType, scan_platform, scan_rom
from models.platform import Platform
from models.rom import Rom
from utils.context import initialize_context


@pytest.mark.vcr
async def test_scan_platform():
    async with initialize_context():
        platform = await scan_platform("n64", ["n64"])

    assert type(platform) is Platform
    assert platform.fs_slug == "n64"
    assert platform.slug == "n64"
    assert platform.name == "Nintendo 64"
    assert platform.igdb_id == 4

    async with initialize_context():
        platform = await scan_platform("", [])

    assert platform.fs_slug == ""
    assert platform.slug == ""
    assert platform.name == ""
    assert platform.igdb_id is None


@pytest.mark.vcr
async def test_scan_rom():
    platform = Platform(fs_slug="n64", igdb_id=4)

    async with initialize_context():
        rom = await scan_rom(
            platform,
            {
                "file_name": "Paper Mario (USA).z64",
                "multi": False,
                "files": ["Paper Mario (USA).z64"],
            },
            ScanType.QUICK,
        )

    assert type(rom) is Rom
    assert rom.file_name == "Paper Mario (USA).z64"
    assert rom.name == "Paper Mario"
    assert rom.igdb_id == 3340
    assert rom.file_size_bytes == 1024
    assert rom.files == ["Paper Mario (USA).z64"]
    assert rom.tags == []
    assert not rom.multi
