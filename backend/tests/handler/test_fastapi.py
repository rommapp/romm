from unittest.mock import AsyncMock, patch

import pytest

from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem.roms_handler import FSRom
from handler.metadata import (
    meta_hasheous_handler,
    meta_moby_handler,
    meta_playmatch_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
)
from handler.metadata.hasheous_handler import HasheousRom
from handler.metadata.ra_handler import RAGameRom
from handler.metadata.ss_handler import SSRom
from handler.scan_handler import (
    MetadataSource,
    ScanType,
    scan_platform,
    scan_rom,
)
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


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_hasheous_handler, "get_ra_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "get_igdb_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_unmatched_replaces_placeholder_name(
    mock_lookup, mock_get_igdb, mock_get_ra, mock_playmatch_enabled
):
    """UNMATCHED scan must replace the placeholder name (the raw filename set
    when the ROM is first created) with a freshly matched provider name,
    instead of keeping the filename (extension included) as the title."""
    hasheous_result = HasheousRom(
        hasheous_id=999,
        igdb_id=None,
        tgdb_id=None,
        ra_id=None,
        name="Snow Bros.",
    )
    mock_lookup.return_value = hasheous_result
    mock_get_igdb.return_value = hasheous_result
    mock_get_ra.return_value = hasheous_result

    platform = Platform(
        id=1, slug="n64", fs_slug="n64", name="Nintendo 64", igdb_id=4, hasheous_id=64
    )
    platform = db_platform_handler.add_platform(platform)

    # Never-matched ROM: name defaults to the raw filename and no provider ids set.
    rom = Rom(
        platform_id=platform.id,
        fs_name="Snow Brothers (USA).zip",
        fs_name_no_tags="Snow Brothers",
        fs_name_no_ext="Snow Brothers (USA)",
        fs_extension="zip",
        fs_path="n64/Snow Brothers (USA)",
        name="Snow Brothers (USA).zip",
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
                "fs_name": "Snow Brothers (USA).zip",
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

    assert result.hasheous_id == 999
    # The placeholder filename must be replaced by the provider name.
    assert result.name == "Snow Bros."


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_hasheous_handler, "get_ra_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "get_igdb_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_unmatched_preserves_custom_name(
    mock_lookup, mock_get_igdb, mock_get_ra, mock_playmatch_enabled
):
    """UNMATCHED scan must keep a user-set name (one that differs from the raw
    filename) rather than overwriting it with a provider name."""
    hasheous_result = HasheousRom(
        hasheous_id=999,
        igdb_id=None,
        tgdb_id=None,
        ra_id=None,
        name="Snow Bros.",
    )
    mock_lookup.return_value = hasheous_result
    mock_get_igdb.return_value = hasheous_result
    mock_get_ra.return_value = hasheous_result

    platform = Platform(
        id=1, slug="n64", fs_slug="n64", name="Nintendo 64", igdb_id=4, hasheous_id=64
    )
    platform = db_platform_handler.add_platform(platform)

    # ROM with a custom name that differs from its filename.
    rom = Rom(
        platform_id=platform.id,
        fs_name="Snow Brothers (USA).zip",
        fs_name_no_tags="Snow Brothers",
        fs_name_no_ext="Snow Brothers (USA)",
        fs_extension="zip",
        fs_path="n64/Snow Brothers (USA)",
        name="My Custom Title",
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
                "fs_name": "Snow Brothers (USA).zip",
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

    assert result.hasheous_id == 999
    # The custom name must be preserved.
    assert result.name == "My Custom Title"


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_hasheous_handler, "get_ra_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "get_igdb_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_unmatched_no_match_uses_parsed_name(
    mock_lookup, mock_get_igdb, mock_get_ra, mock_playmatch_enabled
):
    """UNMATCHED scan that still finds no provider match must heal a raw-filename
    placeholder into the parsed name (tags and extension stripped), so the title
    is clean and a follow-up search uses the parsed name."""
    no_match = HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None)
    mock_lookup.return_value = no_match
    mock_get_igdb.return_value = no_match
    mock_get_ra.return_value = no_match

    platform = Platform(
        id=1, slug="n64", fs_slug="n64", name="Nintendo 64", igdb_id=4, hasheous_id=64
    )
    platform = db_platform_handler.add_platform(platform)

    # Legacy ROM created before the fix: name holds the raw filename.
    rom = Rom(
        platform_id=platform.id,
        fs_name="Snow Brothers (USA).zip",
        fs_name_no_tags="Snow Brothers",
        fs_name_no_ext="Snow Brothers (USA)",
        fs_extension="zip",
        fs_path="n64/Snow Brothers (USA)",
        name="Snow Brothers (USA).zip",
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
                "fs_name": "Snow Brothers (USA).zip",
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

    assert result.hasheous_id is None
    # The raw filename placeholder must be replaced by the parsed name.
    assert result.name == "Snow Brothers"


def _top_level_rom_file(**kwargs) -> RomFile:
    """Build a RomFile whose `is_top_level` cached_property is pre-seeded to
    True, so it passes lookup_rom's filtering without a persisted rom."""
    file = RomFile(file_path="n64/Game", **kwargs)
    file.__dict__["is_top_level"] = True
    return file


@patch.object(meta_hasheous_handler, "_request", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "is_enabled", return_value=True)
async def test_lookup_rom_sends_all_top_level_file_hashes(
    mock_is_enabled, mock_request
):
    """lookup_rom must send the hashes of every top-level file as a list,
    using chd_sha1_hash (and only it) for files that have one, and skipping
    files with no hashes or zero size."""
    mock_request.return_value = {}

    files = [
        _top_level_rom_file(
            file_name="disc1.bin",
            file_size_bytes=100,
            md5_hash="md5one",
            sha1_hash="sha1one",
            crc_hash="crcone",
        ),
        # CHD file: only chd_sha1_hash should be sent, raw md5/crc ignored.
        _top_level_rom_file(
            file_name="disc2.chd",
            file_size_bytes=200,
            md5_hash="ignoredmd5",
            crc_hash="ignoredcrc",
            chd_sha1_hash="chdsha1",
        ),
        # Zero-size file: must be filtered out entirely.
        _top_level_rom_file(
            file_name="empty.bin",
            file_size_bytes=0,
            md5_hash="zeromd5",
        ),
        # No hashes at all: must be skipped.
        _top_level_rom_file(file_name="nohash.bin", file_size_bytes=50),
    ]

    result = await meta_hasheous_handler.lookup_rom("n64", files)

    assert result["hasheous_id"] is None
    mock_request.assert_called_once()
    sent_data = mock_request.call_args.kwargs["data"]
    assert sent_data == [
        {"mD5": "md5one", "shA1": "sha1one", "crc": "crcone"},
        {"shA1": "chdsha1"},
    ]


@patch.object(meta_hasheous_handler, "_request", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "is_enabled", return_value=True)
async def test_lookup_rom_skips_request_when_no_hashes(mock_is_enabled, mock_request):
    """lookup_rom must not hit the API when no file has any usable hash."""
    files = [_top_level_rom_file(file_name="nohash.bin", file_size_bytes=50)]

    result = await meta_hasheous_handler.lookup_rom("n64", files)

    assert result["hasheous_id"] is None
    mock_request.assert_not_called()


def _ss_quota_platform() -> Platform:
    platform = Platform(
        id=1,
        slug="snes",
        fs_slug="snes",
        name="Super Nintendo",
        ss_id=4,
        moby_id=15,
    )
    return db_platform_handler.add_platform(platform)


def _ss_quota_fs_rom(fs_name: str) -> FSRom:
    return {
        "fs_name": fs_name,
        "flat": True,
        "nested": False,
        "files": [],
        "crc_hash": "",
        "md5_hash": "",
        "sha1_hash": "",
        "ra_hash": "",
    }


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_moby_handler, "get_rom", new_callable=AsyncMock)
@patch.object(meta_ss_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_provider_error_does_not_discard_others(
    mock_ss_lookup, mock_moby_get_rom, mock_playmatch_enabled
):
    """An unexpected error from one provider must not wipe the others' results."""
    mock_moby_get_rom.side_effect = ValueError("boom")
    mock_ss_lookup.return_value = (SSRom(ss_id=321, name="Match"), False)

    platform = _ss_quota_platform()
    rom = db_rom_handler.add_rom(
        Rom(platform_id=platform.id, fs_name="game.sfc", fs_path="snes", tags=[])
    )

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.QUICK,
            rom=rom,
            fs_rom=_ss_quota_fs_rom("game.sfc"),
            metadata_sources=[MetadataSource.SS, MetadataSource.MOBY],
            newly_added=True,
        )

    # MobyGames blew up, but ScreenScraper's match survived.
    assert result.ss_id == 321
    assert result.moby_id is None


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_sgdb_handler, "get_details_by_names", new_callable=AsyncMock)
@patch.object(meta_ss_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_sgdb_error_does_not_abort_scan(
    mock_ss_lookup, mock_sgdb_details, mock_playmatch_enabled
):
    """SteamGridDB runs after the other providers; a failure there (issue #2236)
    must not abort the scan or discard the metadata already gathered."""
    mock_ss_lookup.return_value = (SSRom(ss_id=321, name="Match"), False)
    mock_sgdb_details.side_effect = ValueError("boom")

    platform = _ss_quota_platform()
    rom = db_rom_handler.add_rom(
        Rom(platform_id=platform.id, fs_name="game.sfc", fs_path="snes", tags=[])
    )

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.QUICK,
            rom=rom,
            fs_rom=_ss_quota_fs_rom("game.sfc"),
            metadata_sources=[MetadataSource.SS, MetadataSource.SGDB],
            newly_added=True,
        )

    # SteamGridDB was attempted and blew up, but the ROM kept ScreenScraper's match.
    mock_sgdb_details.assert_awaited_once()
    assert type(result) is Rom
    assert result.ss_id == 321
    assert result.sgdb_id is None


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_hasheous_handler, "get_ra_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "get_igdb_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "lookup_rom", new_callable=AsyncMock)
@patch.object(meta_ss_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_hash_match_error_does_not_abort_scan(
    mock_ss_lookup,
    mock_hasheous_lookup,
    mock_hasheous_igdb,
    mock_hasheous_ra,
    mock_playmatch_enabled,
):
    """A failure in the concurrent hash-match step (e.g. Hasheous unreachable,
    issue #2236) must not abort the scan for the ROM."""
    mock_hasheous_lookup.side_effect = ValueError("boom")
    mock_hasheous_igdb.return_value = {}
    mock_hasheous_ra.return_value = {}
    mock_ss_lookup.return_value = (SSRom(ss_id=321, name="Match"), False)

    platform = db_platform_handler.add_platform(
        Platform(
            id=1,
            slug="snes",
            fs_slug="snes",
            name="Super Nintendo",
            ss_id=4,
            hasheous_id=7,
        )
    )
    rom = db_rom_handler.add_rom(
        Rom(platform_id=platform.id, fs_name="game.sfc", fs_path="snes", tags=[])
    )

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.QUICK,
            rom=rom,
            fs_rom=_ss_quota_fs_rom("game.sfc"),
            metadata_sources=[MetadataSource.HASHEOUS, MetadataSource.SS],
            newly_added=True,
        )

    # The Hasheous hash lookup raised, but ScreenScraper still identified the ROM.
    mock_hasheous_lookup.assert_awaited_once()
    assert type(result) is Rom
    assert result.ss_id == 321
    assert result.hasheous_id is None
