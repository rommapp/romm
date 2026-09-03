from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status

from adapters.services.screenscraper import ScreenScraperRateLimitError
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem.roms_handler import FSRom
from handler.metadata import (
    meta_demozoo_handler,
    meta_hasheous_handler,
    meta_igdb_handler,
    meta_moby_handler,
    meta_playmatch_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
)
from handler.metadata.demozoo_handler import DemozooRom
from handler.metadata.hasheous_handler import HasheousMetadata, HasheousRom
from handler.metadata.igdb_handler import IGDBRom
from handler.metadata.ra_handler import RAGameRom
from handler.metadata.ss_handler import (
    SSRom,
    get_rate_limited_rom_names,
    reset_rate_limited_roms,
)
from handler.scan_handler import (
    MetadataSource,
    ScanType,
    scan_platform,
    scan_rom,
)
from models.platform import Platform
from models.rom import Rom, RomFile, SaveTargetLayout
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
    mock_lookup.return_value = (hasheous_result, True)
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


@pytest.mark.parametrize(
    ("stored_title_id", "extracted_title_id"),
    [
        # A first extraction lands on a rom that has no identity yet.
        (None, "0100ABCD12340000"),
        # A hash-only or extraction-disabled rescan must not wipe what is there.
        ("0100ABCD12340000", None),
    ],
)
@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
async def test_scan_rom_folds_extracted_title_id_values(
    mock_playmatch_enabled,
    stored_title_id: str | None,
    extracted_title_id: str | None,
):
    platform = Platform(id=1, slug="switch", fs_slug="switch", name="Nintendo Switch")
    platform = db_platform_handler.add_platform(platform)

    rom = Rom(
        platform_id=platform.id,
        fs_name="Game.nsp",
        fs_path="switch/roms",
        name="Game",
        fs_size_bytes=1024,
        tags=[],
        title_id=stored_title_id,
        save_target=stored_title_id,
        save_target_layout=(SaveTargetLayout.FOLDER_EXACT if stored_title_id else None),
    )
    rom = db_rom_handler.add_rom(rom)

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.QUICK,
            rom=rom,
            fs_rom={
                "fs_name": "Game.nsp",
                "flat": True,
                "nested": False,
                "files": [
                    RomFile(
                        rom=rom,
                        file_name="Game.nsp",
                        file_path="switch/roms",
                        file_size_bytes=1024,
                        last_modified=1620000000,
                    )
                ],
                "crc_hash": "",
                "md5_hash": "",
                "sha1_hash": "",
                "ra_hash": "",
                "title_id": extracted_title_id,
                "save_target": extracted_title_id,
                "save_target_layout": (
                    SaveTargetLayout.FOLDER_EXACT if extracted_title_id else None
                ),
            },
            metadata_sources=[],
            newly_added=False,
        )

    assert result.title_id == "0100ABCD12340000"
    assert result.save_target == "0100ABCD12340000"
    assert result.save_target_layout == SaveTargetLayout.FOLDER_EXACT


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
    mock_lookup.return_value = (hasheous_result, True)
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
    mock_lookup.return_value = (hasheous_result, True)
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
    mock_lookup.return_value = (no_match, True)
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


def _scraped_cover_rom(platform: Platform, **overrides) -> Rom:
    attrs: dict = {
        "platform_id": platform.id,
        "fs_name": "game.sfc",
        "fs_path": "snes",
        "tags": [],
        "ss_id": 321,
        "name": "Game",
        "url_cover": "https://ss.fr/media?media=box-2D&id=old",
        "path_cover_s": "roms/1/1/cover/small.png",
        "path_cover_l": "roms/1/1/cover/big.png",
    }
    attrs.update(overrides)
    return db_rom_handler.add_rom(Rom(**attrs))


NEW_COVER_URL = "https://ss.fr/media?media=box-2D&id=new"


def _ss_returns_new_cover(mock_ss_get_by_id: AsyncMock) -> None:
    mock_ss_get_by_id.return_value = SSRom(
        ss_id=321, name="Game", url_cover=NEW_COVER_URL
    )


async def _update_scan(platform: Platform, rom: Rom) -> Rom:
    async with initialize_context():
        return await scan_rom(
            platform=platform,
            scan_type=ScanType.UPDATE,
            rom=rom,
            fs_rom=_ss_quota_fs_rom("game.sfc"),
            metadata_sources=[MetadataSource.SS],
            newly_added=False,
        )


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_ss_handler, "get_rom_by_id", new_callable=AsyncMock)
async def test_update_scan_replaces_scraped_cover_url(
    mock_ss_get_by_id, mock_playmatch_enabled
):
    """A cover that carries a source url came from a provider, so an UPDATE scan
    hands the freshly resolved url downstream. Pinning it to the stored value is
    what kept a changed source priority from ever reaching the download step."""
    _ss_returns_new_cover(mock_ss_get_by_id)

    platform = _ss_quota_platform()
    rom = _scraped_cover_rom(platform)

    result = await _update_scan(platform, rom)

    assert result.url_cover == NEW_COVER_URL


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_ss_handler, "get_rom_by_id", new_callable=AsyncMock)
async def test_update_scan_keeps_uploaded_cover(
    mock_ss_get_by_id, mock_playmatch_enabled
):
    """Uploading artwork locks the cover, so the provider url must not be adopted
    over it."""
    _ss_returns_new_cover(mock_ss_get_by_id)

    platform = _ss_quota_platform()
    rom = _scraped_cover_rom(platform, url_cover="", locked_fields=["url_cover"])

    result = await _update_scan(platform, rom)

    assert result.url_cover == ""
    assert result.locked_fields == ["url_cover"]


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_ss_handler, "get_rom_by_id", new_callable=AsyncMock)
async def test_update_scan_keeps_locked_cover_with_no_stored_path(
    mock_ss_get_by_id, mock_playmatch_enabled
):
    """The lock has to outlive path_cover_s. That column tracks the filesystem and
    a scan clears it whenever the file is unreadable, so inferring the lock from it
    meant one scan against unavailable storage handed the cover to the provider."""
    _ss_returns_new_cover(mock_ss_get_by_id)

    platform = _ss_quota_platform()
    rom = _scraped_cover_rom(
        platform,
        url_cover="",
        path_cover_s="",
        path_cover_l="",
        locked_fields=["url_cover"],
    )

    result = await _update_scan(platform, rom)

    assert result.url_cover == ""


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_ss_handler, "get_rom_by_id", new_callable=AsyncMock)
async def test_update_scan_replaces_screenshot_urls(
    mock_ss_get_by_id, mock_playmatch_enabled
):
    """Screenshots have no upload path, so a stored set is always provider-written
    and the fresh set wins."""
    mock_ss_get_by_id.return_value = SSRom(
        ss_id=321,
        name="Game",
        url_screenshots=["https://ss.fr/ss?id=new"],
    )

    platform = _ss_quota_platform()
    rom = _scraped_cover_rom(
        platform,
        url_screenshots=["https://ss.fr/ss?id=old"],
        path_screenshots=["roms/1/1/screenshots/0.png"],
    )

    result = await _update_scan(platform, rom)

    assert result.url_screenshots == ["https://ss.fr/ss?id=new"]


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_ss_handler, "get_rom_by_id", new_callable=AsyncMock)
async def test_update_scan_keeps_name_summary_and_manual(
    mock_ss_get_by_id, mock_playmatch_enabled
):
    """Text fields and manuals stay pinned. Neither can yet tell a hand-edited
    value from a provider-written one, so freeing the artwork urls must not free
    these too."""
    mock_ss_get_by_id.return_value = SSRom(
        ss_id=321,
        name="Provider Name",
        summary="Provider summary",
        url_manual="https://ss.fr/manual?id=new",
    )

    platform = _ss_quota_platform()
    rom = _scraped_cover_rom(
        platform,
        name="My Title",
        summary="My summary",
        url_manual="https://ss.fr/manual?id=old",
        path_manual="roms/1/1/manual/1.pdf",
    )

    result = await _update_scan(platform, rom)

    assert result.name == "My Title"
    assert result.summary == "My summary"
    assert result.url_manual == "https://ss.fr/manual?id=old"


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_hasheous_handler, "get_ra_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "get_igdb_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_hashes_rematches_hasheous(
    mock_lookup, mock_get_igdb, mock_get_ra, mock_playmatch_enabled
):
    """A HASHES rescan must re-run the Hasheous hash lookup, so a ROM whose
    hashes were wrong picks up its signature matches (the verified flags)
    without needing a complete rescan."""
    hasheous_result = HasheousRom(
        hasheous_id=999,
        igdb_id=None,
        tgdb_id=None,
        ra_id=None,
        name="Snow Bros.",
        hasheous_metadata=HasheousMetadata(
            tosec_match=False,
            mame_arcade_match=False,
            mame_mess_match=False,
            nointro_match=True,
            redump_match=False,
            mame_redump_match=False,
            whdload_match=False,
            ra_match=True,
            fbneo_match=False,
            puredos_match=False,
        ),
    )
    mock_lookup.return_value = (hasheous_result, True)
    mock_get_igdb.return_value = hasheous_result
    mock_get_ra.return_value = hasheous_result

    platform = Platform(
        id=1, slug="n64", fs_slug="n64", name="Nintendo 64", igdb_id=4, hasheous_id=64
    )
    platform = db_platform_handler.add_platform(platform)

    # ROM that never matched Hasheous because its hashes were wrong.
    rom = Rom(
        platform_id=platform.id,
        fs_name="Snow Brothers (USA).7z",
        fs_name_no_tags="Snow Brothers",
        fs_name_no_ext="Snow Brothers (USA)",
        fs_extension="7z",
        fs_path="n64/Snow Brothers (USA)",
        name="My Custom Title",
        hasheous_id=None,
        hasheous_metadata={},
        fs_size_bytes=1024,
        tags=[],
    )
    rom = db_rom_handler.add_rom(rom)

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.HASHES,
            rom=rom,
            fs_rom={
                "fs_name": "Snow Brothers (USA).7z",
                "flat": True,
                "nested": False,
                "files": [],
                "crc_hash": "newcrc",
                "md5_hash": "newmd5",
                "sha1_hash": "newsha1",
                "ra_hash": "newrahash",
            },
            metadata_sources=[MetadataSource.HASHEOUS],
            newly_added=False,
        )

    mock_lookup.assert_called_once()
    assert result.hasheous_id == 999
    assert result.hasheous_metadata["nointro_match"] is True
    assert result.hasheous_metadata["ra_match"] is True
    # A rehash must not rewrite user-visible fields.
    assert result.name == "My Custom Title"


def _stale_hasheous_rom(platform: Platform) -> Rom:
    """A ROM carrying a Hasheous match (and its verification flags) earned by
    hashes it is about to lose."""
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            fs_name="Snow Brothers (USA).7z",
            fs_name_no_tags="Snow Brothers",
            fs_name_no_ext="Snow Brothers (USA)",
            fs_extension="7z",
            fs_path="n64/Snow Brothers (USA)",
            name="Snow Bros.",
            hasheous_id=999,
            hasheous_metadata={"nointro_match": True, "ra_match": True},
            fs_size_bytes=1024,
            tags=[],
        )
    )


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_hasheous_handler, "get_ra_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "get_igdb_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_hashes_clears_stale_hasheous_match(
    mock_lookup, mock_get_igdb, mock_get_ra, mock_playmatch_enabled
):
    """A HASHES rescan whose new hashes no longer match must drop the previous
    Hasheous match, so the ROM stops reporting verification flags it earned with
    hashes it no longer has."""
    no_match = HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None)
    # Hasheous answered and knows nothing about the new hashes.
    mock_lookup.return_value = (no_match, True)
    mock_get_igdb.return_value = no_match
    mock_get_ra.return_value = no_match

    platform = db_platform_handler.add_platform(
        Platform(
            id=1,
            slug="n64",
            fs_slug="n64",
            name="Nintendo 64",
            igdb_id=4,
            hasheous_id=64,
        )
    )
    rom = _stale_hasheous_rom(platform)

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.HASHES,
            rom=rom,
            fs_rom={
                "fs_name": "Snow Brothers (USA).7z",
                "flat": True,
                "nested": False,
                "files": [],
                "crc_hash": "changedcrc",
                "md5_hash": "changedmd5",
                "sha1_hash": "changedsha1",
                "ra_hash": "",
            },
            metadata_sources=[MetadataSource.HASHEOUS],
            newly_added=False,
        )

    assert result.hasheous_id is None
    assert result.hasheous_metadata == {}


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_hasheous_handler, "get_ra_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "get_igdb_game", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_hashes_keeps_match_when_hasheous_unreachable(
    mock_lookup, mock_get_igdb, mock_get_ra, mock_playmatch_enabled
):
    """An inconclusive lookup (Hasheous down, no hashes to send) must leave the
    existing match alone, so an outage can't silently de-verify a library."""
    no_match = HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None)
    # Same empty match, but we never got an answer.
    mock_lookup.return_value = (no_match, False)
    mock_get_igdb.return_value = no_match
    mock_get_ra.return_value = no_match

    platform = db_platform_handler.add_platform(
        Platform(
            id=1,
            slug="n64",
            fs_slug="n64",
            name="Nintendo 64",
            igdb_id=4,
            hasheous_id=64,
        )
    )
    rom = _stale_hasheous_rom(platform)

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.HASHES,
            rom=rom,
            fs_rom={
                "fs_name": "Snow Brothers (USA).7z",
                "flat": True,
                "nested": False,
                "files": [],
                "crc_hash": "changedcrc",
                "md5_hash": "changedmd5",
                "sha1_hash": "changedsha1",
                "ra_hash": "",
            },
            metadata_sources=[MetadataSource.HASHEOUS],
            newly_added=False,
        )

    assert result.hasheous_id == 999
    assert result.hasheous_metadata == {"nointro_match": True, "ra_match": True}


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

    result, conclusive = await meta_hasheous_handler.lookup_rom("n64", files)

    assert result["hasheous_id"] is None
    # Hasheous answered, it just knows nothing about these hashes.
    assert conclusive is True
    mock_request.assert_called_once()
    sent_data = mock_request.call_args.kwargs["data"]
    assert sent_data == [
        {"mD5": "md5one", "shA1": "sha1one", "crc": "crcone"},
        {"shA1": "chdsha1"},
    ]


@patch.object(meta_hasheous_handler, "_request", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "is_enabled", return_value=True)
async def test_lookup_rom_sends_the_largest_archive_member_hashes(
    mock_is_enabled, mock_request
):
    """Hasheous indexes a multi-file archive by the ROM inside it, so the
    archive's composite hash must not be what we ask about."""
    mock_request.return_value = {}

    files = [
        _top_level_rom_file(
            file_name="set.zip",
            file_size_bytes=300,
            crc_hash="compositecrc",
            md5_hash="compositemd5",
            sha1_hash="compositesha1",
            archive_members=[
                {
                    "name": "readme.txt",
                    "size": 10,
                    "crc_hash": "readmecrc",
                    "md5_hash": "readmemd5",
                    "sha1_hash": "readmesha1",
                },
                {
                    "name": "game.n64",
                    "size": 2048,
                    "crc_hash": "gamecrc",
                    "md5_hash": "gamemd5",
                    "sha1_hash": "gamesha1",
                },
            ],
        ),
    ]

    await meta_hasheous_handler.lookup_rom("n64", files)

    sent_data = mock_request.call_args.kwargs["data"]
    assert sent_data == [{"mD5": "gamemd5", "shA1": "gamesha1", "crc": "gamecrc"}]


@patch.object(meta_hasheous_handler, "_request", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "is_enabled", return_value=True)
async def test_lookup_rom_maps_every_hasheous_signature_source(
    mock_is_enabled, mock_request
):
    """Each match flag reads a Hasheous SignatureSourceType name verbatim, so a
    typo silently pins that flag to False."""
    mock_request.return_value = {
        "id": 1,
        "signatures": {
            "TOSEC": {},
            "MAMEArcade": {},
            "MAMEMess": {},
            "NoIntros": {},
            "Redump": {},
            "MAMERedump": {},
            "WHDLoad": {},
            "RetroAchievements": {},
            "FBNeo": {},
            "PureDOSDAT": {},
        },
    }

    files = [
        _top_level_rom_file(file_name="game.n64", file_size_bytes=100, md5_hash="md5")
    ]

    result, _ = await meta_hasheous_handler.lookup_rom("n64", files)

    assert all(result["hasheous_metadata"].values())


@patch.object(meta_hasheous_handler, "_request", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "is_enabled", return_value=True)
async def test_lookup_rom_marks_a_chd_matched_by_mameredump_as_verified(
    mock_is_enabled, mock_request
):
    """Hasheous indexes CHD conversions under MAMERedump, not Redump, so a CHD
    match sets no other flag and the ROM would otherwise never read as
    verified."""
    mock_request.return_value = {"id": 1, "signatures": {"MAMERedump": {}}}

    files = [
        _top_level_rom_file(
            file_name="game.chd", file_size_bytes=100, chd_sha1_hash="discsha1"
        )
    ]

    result, _ = await meta_hasheous_handler.lookup_rom("dc", files)

    assert result["hasheous_metadata"]["mame_redump_match"] is True


@patch.object(meta_hasheous_handler, "_request", new_callable=AsyncMock)
@patch.object(meta_hasheous_handler, "is_enabled", return_value=True)
async def test_lookup_rom_skips_request_when_no_hashes(mock_is_enabled, mock_request):
    """lookup_rom must not hit the API when no file has any usable hash."""
    files = [_top_level_rom_file(file_name="nohash.bin", file_size_bytes=50)]

    result, conclusive = await meta_hasheous_handler.lookup_rom("n64", files)

    assert result["hasheous_id"] is None
    # Nothing was asked, so the empty match says nothing about the ROM.
    assert conclusive is False
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
@patch.object(meta_sgdb_handler, "is_enabled", return_value=True)
@patch.object(meta_sgdb_handler.sgdb_service, "search_games", new_callable=AsyncMock)
@patch.object(meta_ss_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_sgdb_error_does_not_abort_scan(
    mock_ss_lookup, mock_sgdb_search, mock_sgdb_enabled, mock_playmatch_enabled
):
    """SteamGridDB runs after the other providers; a failure there (issue #2236)
    must resolve to an empty match in the handler instead of aborting the scan
    or discarding the metadata already gathered."""
    mock_ss_lookup.return_value = (SSRom(ss_id=321, name="Match"), False)
    mock_sgdb_search.side_effect = ValueError("boom")

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
    mock_sgdb_search.assert_awaited_once()
    assert type(result) is Rom
    assert result.ss_id == 321
    assert result.sgdb_id is None


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_hasheous_handler, "is_enabled", return_value=True)
@patch.object(meta_hasheous_handler, "_request", new_callable=AsyncMock)
@patch.object(meta_ss_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_hash_match_error_does_not_abort_scan(
    mock_ss_lookup,
    mock_hasheous_request,
    mock_hasheous_enabled,
    mock_playmatch_enabled,
):
    """A failure in the concurrent hash-match step (e.g. Hasheous unreachable,
    issue #2236) must resolve to an empty match in the handler instead of
    aborting the scan for the ROM."""
    mock_hasheous_request.side_effect = HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Can't connect to Hasheous, check your internet connection",
    )
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
    fs_rom = _ss_quota_fs_rom("game.sfc")
    fs_rom["files"] = [
        _top_level_rom_file(
            file_name="game.sfc",
            file_size_bytes=1024,
            md5_hash="somemd5hash",
        )
    ]

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.QUICK,
            rom=rom,
            fs_rom=fs_rom,
            metadata_sources=[MetadataSource.HASHEOUS, MetadataSource.SS],
            newly_added=True,
        )

    # The Hasheous hash lookup raised, but ScreenScraper still identified the ROM.
    mock_hasheous_request.assert_awaited_once()
    assert type(result) is Rom
    assert result.ss_id == 321
    assert result.hasheous_id is None


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_ss_handler, "get_rom", new_callable=AsyncMock)
@patch.object(meta_ss_handler, "lookup_rom", new_callable=AsyncMock)
async def test_scan_rom_ss_rate_limit_skips_the_rom_without_further_lookups(
    mock_ss_lookup, mock_ss_get_rom, mock_playmatch_enabled
):
    """The per-minute budget is already spent, so the name-search fallback would
    only burn another retried request. Record the ROM and move on."""
    reset_rate_limited_roms()
    mock_ss_lookup.side_effect = ScreenScraperRateLimitError()

    platform = db_platform_handler.add_platform(
        Platform(id=1, slug="snes", fs_slug="snes", name="SNES", ss_id=4)
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
            metadata_sources=[MetadataSource.SS],
            newly_added=True,
        )

    mock_ss_lookup.assert_awaited_once()
    mock_ss_get_rom.assert_not_awaited()
    assert result.ss_id is None
    assert get_rate_limited_rom_names() == ["game.sfc"]

    reset_rate_limited_roms()


def _amiga_platform() -> Platform:
    return db_platform_handler.add_platform(
        Platform(
            id=1,
            slug="amiga",
            fs_slug="amiga",
            name="Commodore Amiga",
            igdb_id=16,
        )
    )


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_sgdb_handler, "get_details_by_names", new_callable=AsyncMock)
@patch.object(meta_igdb_handler, "get_rom", new_callable=AsyncMock)
@patch.object(meta_demozoo_handler, "get_rom", new_callable=AsyncMock)
async def test_scan_rom_scene_match_ignores_similar_game_cover(
    mock_demozoo_get_rom, mock_igdb_get_rom, mock_sgdb_names, mock_playmatch_enabled
):
    """A Demozoo hit must not pick up IGDB/SGDB art for a similarly named game."""
    mock_demozoo_get_rom.return_value = DemozooRom(
        demozoo_id=2,
        name="State of the Art",
        summary="Demo by Spaceballs (1992)",
        url_cover="https://demozoo.org/media/sota.png",
        url_screenshots=["https://demozoo.org/media/sota.png"],
    )
    mock_igdb_get_rom.return_value = IGDBRom(
        igdb_id=99901,
        name="State of the Art",
        summary="A skateboarding game",
        url_cover="https://images.igdb.com/skate.jpg",
    )
    mock_sgdb_names.return_value = {
        "sgdb_id": 42,
        "url_cover": "https://cdn.steamgriddb.com/skate.png",
    }

    platform = _amiga_platform()
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            fs_name="State of the Art (demozoo-2).adf",
            fs_path="amiga",
            tags=[],
        )
    )

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.QUICK,
            rom=rom,
            fs_rom=_ss_quota_fs_rom("State of the Art (demozoo-2).adf"),
            metadata_sources=[
                MetadataSource.DEMOZOO,
                MetadataSource.IGDB,
                MetadataSource.SGDB,
            ],
            newly_added=True,
        )

    assert result.demozoo_id == 2
    assert result.name == "State of the Art"
    assert result.summary == "Demo by Spaceballs (1992)"
    assert result.url_cover == "https://demozoo.org/media/sota.png"
    assert result.igdb_id is None
    assert result.sgdb_id is None
    mock_sgdb_names.assert_not_awaited()


@patch.object(meta_playmatch_handler, "is_enabled", return_value=False)
@patch.object(meta_igdb_handler, "get_rom", new_callable=AsyncMock)
@patch.object(meta_demozoo_handler, "get_rom", new_callable=AsyncMock)
async def test_scan_rom_games_still_use_fuzzy_catalog_covers(
    mock_demozoo_get_rom, mock_igdb_get_rom, mock_playmatch_enabled
):
    """Retail games with no scene id keep IGDB-style similar-title covers."""
    mock_demozoo_get_rom.return_value = DemozooRom(demozoo_id=None)
    mock_igdb_get_rom.return_value = IGDBRom(
        igdb_id=3340,
        name="Paper Mario",
        url_cover="https://images.igdb.com/paper-mario.jpg",
    )

    platform = _amiga_platform()
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            fs_name="Paper Mario (USA).z64",
            fs_path="amiga",
            tags=[],
        )
    )

    async with initialize_context():
        result = await scan_rom(
            platform=platform,
            scan_type=ScanType.QUICK,
            rom=rom,
            fs_rom=_ss_quota_fs_rom("Paper Mario (USA).z64"),
            metadata_sources=[MetadataSource.DEMOZOO, MetadataSource.IGDB],
            newly_added=True,
        )

    assert result.demozoo_id is None
    assert result.igdb_id == 3340
    assert result.name == "Paper Mario"
    assert result.url_cover == "https://images.igdb.com/paper-mario.jpg"
