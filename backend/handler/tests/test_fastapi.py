import pytest
from handler.scan_handler import MetadataSource, ScanType, scan_platform, scan_rom
from models.platform import Platform
from models.rom import Rom, RomFile
from utils.context import initialize_context


@pytest.mark.vcr(record_mode="all")
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


@pytest.mark.vcr(record_mode="all")
async def test_scan_rom():
    platform = Platform(fs_slug="n64", igdb_id=4)
    rom = Rom(
        fs_name="Paper Mario (USA).z64",
        name="Paper Mario",
        igdb_id=3340,
        fs_size_bytes=1024,
        tags=[],
        multi=False,
    )

    async with initialize_context():
        rom = await scan_rom(
            platform=platform,
            scan_type=ScanType.QUICK,
            rom=rom,
            fs_rom={
                "fs_name": "Paper Mario (USA).z64",
                "multi": False,
                "files": [
                    RomFile(
                        file_name="Paper Mario (USA).z64",
                        file_path="n64/Paper Mario (USA)",
                        file_size_bytes=1024,
                        last_modified=1620000000,
                    )
                ],
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
                "ra_hash": "",
            },
            metadata_sources=[MetadataSource.IGDB],
            newly_added=True,
        )

    assert type(rom) is Rom
    assert rom.fs_name == "Paper Mario (USA).z64"
    assert rom.name == "Paper Mario"
    assert rom.igdb_id == 3340
    assert rom.fs_size_bytes == 1024
    assert rom.tags == []
    assert not rom.multi
