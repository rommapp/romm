from unittest.mock import AsyncMock, patch

import pytest

from handler.database import db_platform_handler, db_rom_handler
from handler.metadata import (
    meta_hasheous_handler,
    meta_playmatch_handler,
    meta_ra_handler,
)
from handler.metadata.hasheous_handler import HasheousRom
from handler.metadata.ra_handler import RAGameRom
from handler.scan_handler import MetadataSource, ScanType, scan_platform, scan_rom
from models.platform import Platform
from models.rom import Rom, RomFile
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
    assert platform.hasheous_id == 64
    # Hasheous returns tgdb_id=None and Moby has no tgdb_id for n64, so
    # this value must come from the TGDB handler fallback.
    assert platform.tgdb_id == 3

    async with initialize_context():
        platform = await scan_platform("", [])

    assert platform.fs_slug == ""
    assert platform.slug == ""
    assert platform.name == ""
    assert platform.igdb_id is None
    assert platform.hasheous_id is None
    assert platform.tgdb_id is None


@pytest.mark.vcr
async def test_scan_rom():
    platform = Platform(
        id=1, slug="n64", fs_slug="n64", name="Nintendo 64", igdb_id=4, hasheous_id=64
    )
    platform = db_platform_handler.add_platform(platform)

    rom = Rom(
        platform_id=platform.id,
        fs_name="Paper Mario (USA).z64",
        fs_name_no_tags="Paper Mario",
        fs_name_no_ext="Paper Mario",
        fs_extension="z64",
        fs_path="n64/Paper Mario (USA)",
        name="Paper Mario",
        igdb_id=3340,
        hasheous_id=4872,
        fs_size_bytes=1024,
        tags=[],
    )

    async with initialize_context():
        rom = await scan_rom(
            platform=platform,
            scan_type=ScanType.QUICK,
            rom=rom,
            fs_rom={
                "fs_name": "Paper Mario (USA).z64",
                "flat": True,
                "nested": False,
                "files": [
                    RomFile(
                        rom=rom,
                        file_name="Paper Mario (USA).z64",
                        file_path="n64/Paper Mario (USA)",
                        file_size_bytes=23175094,
                        last_modified=1620000000,
                        crc_hash="d56d1c89",
                        md5_hash="7de64234ee20788b9d74d2fdb3462aed",
                        sha1_hash="77693a00418a9d8971b7a005f2001d997e359bff",
                    )
                ],
                "crc_hash": "d56d1c89",
                "md5_hash": "7de64234ee20788b9d74d2fdb3462aed",
                "sha1_hash": "77693a00418a9d8971b7a005f2001d997e359bff",
                "ra_hash": "",
            },
            metadata_sources=[MetadataSource.HASHEOUS],
            newly_added=True,
        )

    assert type(rom) is Rom
    assert rom.fs_name == "Paper Mario (USA).z64"
    assert rom.fs_path == "n64/Paper Mario (USA)"
    # Disabled until we can fix the tests
    # assert rom.name == "Paper Mario"
    # assert rom.igdb_id == 3340
    # assert rom.hasheous_id == 4872
    # assert rom.fs_size_bytes == 23175094
    # assert rom.tags == []


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_hasheous_handler, "get_ra_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "get_igdb_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_complete_clears_unselected_metadata(
    mock_lookup, mock_get_igdb, mock_get_ra, mock_playmatch_enabled
):
    """COMPLETE rescan with newly_added=False must clear id and *_metadata
    fields for sources that are no longer in metadata_sources."""
    hasheous_result = HasheousRom(
        hasheous_id=999,
        igdb_id=None,
        tgdb_id=None,
        ra_id=None,
        name="Mock Hasheous Game",
    )
    mock_lookup.return_value = hasheous_result
    mock_get_igdb.return_value = hasheous_result
    mock_get_ra.return_value = hasheous_result

    platform = Platform(
        id=1,
        slug="n64",
        fs_slug="n64",
        name="Nintendo 64",
        igdb_id=4,
        ra_id=2,
        hasheous_id=64,
    )
    platform = db_platform_handler.add_platform(platform)

    rom = Rom(
        platform_id=platform.id,
        fs_name="Paper Mario (USA).z64",
        fs_name_no_tags="Paper Mario",
        fs_name_no_ext="Paper Mario",
        fs_extension="z64",
        fs_path="n64/Paper Mario (USA)",
        name="Paper Mario",
        igdb_id=3340,
        igdb_metadata={"summary": "stale IGDB metadata"},
        ra_id=1234,
        ra_metadata={"name": "stale RA metadata"},
        hasheous_id=4872,
        fs_size_bytes=1024,
        tags=[],
    )
    rom = db_rom_handler.add_rom(rom)

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.COMPLETE,
            rom=rom,
            fs_rom={
                "fs_name": "Paper Mario (USA).z64",
                "flat": True,
                "nested": False,
                "files": [],
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
                "ra_hash": "",
            },
            metadata_sources=[MetadataSource.HASHEOUS],
            newly_added=False,
        )

    # IGDB and RA were unselected — their id and metadata must be cleared.
    assert result.igdb_id is None
    assert result.igdb_metadata == {}
    assert result.ra_id is None
    assert result.ra_metadata == {}
    # Hasheous is still selected and should remain populated.
    assert result.hasheous_id == 999


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_ra_handler, "get_rom_by_id", new_callable=AsyncMock)
@patch.object(meta_ra_handler, "get_rom", new_callable=AsyncMock)
async def test_scan_rom_unmatched_fetches_ra_when_id_set_but_no_metadata(
    mock_get_rom, mock_get_rom_by_id, mock_playmatch_enabled
):
    """UNMATCHED scan must fetch RA metadata when ra_id is set manually but
    ra_metadata is empty (the user manually set the ID)."""
    ra_result = RAGameRom(
        ra_id=2774,
        name="Jak and Daxter: The Precursor's Legacy",
        url_cover="https://media.retroachievements.org/Images/jpg",
    )
    mock_get_rom_by_id.return_value = ra_result
    mock_get_rom.return_value = RAGameRom(ra_id=None)

    platform = Platform(
        id=1,
        slug="ps2",
        fs_slug="ps2",
        name="PlayStation 2",
        igdb_id=8,
        ra_id=21,
    )
    platform = db_platform_handler.add_platform(platform)

    # ROM has ra_id set manually but no ra_metadata (never fetched before)
    rom = Rom(
        platform_id=platform.id,
        fs_name="Jak and Daxter.chd",
        fs_name_no_tags="Jak and Daxter",
        fs_name_no_ext="Jak and Daxter",
        fs_extension="chd",
        fs_path="ps2",
        name="Jak and Daxter",
        ra_id=2774,
        ra_metadata={},  # empty - never fetched
        fs_size_bytes=1024,
        tags=[],
    )
    rom = db_rom_handler.add_rom(rom)

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.UNMATCHED,
            rom=rom,
            fs_rom={
                "fs_name": "Jak and Daxter.chd",
                "flat": True,
                "nested": False,
                "files": [],
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
                "ra_hash": "",
            },
            metadata_sources=[MetadataSource.RA],
            newly_added=False,
        )

    # ra_id was set manually - get_rom_by_id should be called, not get_rom
    mock_get_rom_by_id.assert_called_once()
    mock_get_rom.assert_not_called()
    assert result.ra_id == 2774


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_ra_handler, "get_rom_by_id", new_callable=AsyncMock)
@patch.object(meta_ra_handler, "get_rom", new_callable=AsyncMock)
async def test_scan_rom_unmatched_skips_ra_when_id_and_metadata_exist(
    mock_get_rom, mock_get_rom_by_id, mock_playmatch_enabled
):
    """UNMATCHED scan must NOT re-fetch RA metadata when both ra_id and
    ra_metadata are already populated."""
    mock_get_rom_by_id.return_value = RAGameRom(ra_id=None)
    mock_get_rom.return_value = RAGameRom(ra_id=None)

    platform = Platform(
        id=1,
        slug="ps2",
        fs_slug="ps2",
        name="PlayStation 2",
        igdb_id=8,
        ra_id=21,
    )
    platform = db_platform_handler.add_platform(platform)

    # ROM has both ra_id and ra_metadata populated
    rom = Rom(
        platform_id=platform.id,
        fs_name="Jak and Daxter.chd",
        fs_name_no_tags="Jak and Daxter",
        fs_name_no_ext="Jak and Daxter",
        fs_extension="chd",
        fs_path="ps2",
        name="Jak and Daxter",
        ra_id=2774,
        ra_metadata={"achievements_count": 60},  # already populated
        fs_size_bytes=1024,
        tags=[],
    )
    rom = db_rom_handler.add_rom(rom)

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.UNMATCHED,
            rom=rom,
            fs_rom={
                "fs_name": "Jak and Daxter.chd",
                "flat": True,
                "nested": False,
                "files": [],
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
                "ra_hash": "",
            },
            metadata_sources=[MetadataSource.RA],
            newly_added=False,
        )

    # Both ID and metadata exist - should not re-fetch
    mock_get_rom_by_id.assert_not_called()
    mock_get_rom.assert_not_called()
    # Existing ra_id should be preserved
    assert result.ra_id == 2774
