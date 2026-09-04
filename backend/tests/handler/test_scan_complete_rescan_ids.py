"""What a complete rescan does to a ROM's external IDs.

A complete rescan is documented as wiping every match and rematching from
scratch, but `add_rom` merges, and merge skips attributes the object doesn't
carry. An ID therefore only resets when the scan writes it out as NULL, which
it did for deselected sources but not for the ones it actually searched. (#4346)

The flip side matters just as much: a provider that failed answered nothing, so
its ID has to survive. Several report an outage as an empty match, which a
rescan would otherwise read as "this game is gone".
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from handler.database import db_platform_handler, db_rom_handler
from handler.metadata.igdb_handler import IGDBRom
from handler.metadata.pouet_handler import PouetRom
from handler.metadata.sgdb_handler import SGDBRom
from handler.metadata.ss_handler import SSRom
from handler.scan_handler import MetadataSource, ScanType, scan_rom
from models.platform import Platform
from models.rom import Rom
from utils.context import initialize_context

FS_NAME = "Some Homebrew Thing (Aftermarket).z64"
STALE_IGDB_ID = 1289
STALE_MOBY_ID = 42
STALE_SGDB_ID = 777
STALE_POUET_ID = 106640
STALE_SS_ID = 314

MISS = IGDBRom(igdb_id=None)
MATCH = IGDBRom(igdb_id=9999, name="A Real Game")
UNREACHABLE = HTTPException(status_code=503, detail="provider is down")


def _lookup(result):
    """A provider lookup that answers with `result`, or fails when it is one."""
    if isinstance(result, Exception):
        return AsyncMock(side_effect=result)
    return AsyncMock(return_value=result)


async def _complete_rescan(
    sources: list[str],
    *,
    igdb_result: IGDBRom | Exception = MISS,
    sgdb_result: SGDBRom | Exception | None = None,
    pouet_result: PouetRom | Exception | None = None,
    platform_igdb_id: int | None = 4,
    ss_breaker_tripped: bool = False,
) -> Rom:
    """Run a complete rescan over a ROM carrying hand-set IDs, and persist it."""
    platform = db_platform_handler.add_platform(
        Platform(
            id=1,
            slug="n64",
            fs_slug="n64",
            name="Nintendo 64",
            igdb_id=platform_igdb_id,
            ss_id=14,
        )
    )
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            fs_name=FS_NAME,
            fs_name_no_tags="Some Homebrew Thing",
            fs_name_no_ext="Some Homebrew Thing (Aftermarket)",
            fs_extension="z64",
            fs_path="n64",
            name="Wrong Match",
            igdb_id=STALE_IGDB_ID,
            igdb_metadata={"total_rating": "9"},
            moby_id=STALE_MOBY_ID,
            sgdb_id=STALE_SGDB_ID,
            pouet_id=STALE_POUET_ID,
            ss_id=STALE_SS_ID,
            fs_size_bytes=1024,
            tags=[],
        )
    )

    igdb_mock = _lookup(igdb_result)
    pouet_mock = _lookup(pouet_result or PouetRom(pouet_id=None))
    with (
        patch("handler.scan_handler.meta_igdb_handler.get_rom", new=igdb_mock),
        patch("handler.scan_handler.meta_igdb_handler.get_rom_by_id", new=igdb_mock),
        patch(
            "handler.scan_handler.meta_sgdb_handler.get_details_by_names",
            new=_lookup(sgdb_result or SGDBRom(sgdb_id=None)),
        ),
        patch("handler.scan_handler.meta_pouet_handler.get_rom", new=pouet_mock),
        patch("handler.scan_handler.meta_pouet_handler.get_rom_by_id", new=pouet_mock),
        patch(
            "handler.scan_handler.meta_ss_handler.lookup_rom",
            new=AsyncMock(return_value=(SSRom(ss_id=None), False)),
        ),
        patch(
            "handler.scan_handler.meta_ss_handler.get_rom",
            new=AsyncMock(return_value=SSRom(ss_id=None)),
        ),
        patch(
            "handler.scan_handler.is_breaker_tripped",
            return_value=ss_breaker_tripped,
        ),
    ):
        async with initialize_context():
            scanned = await scan_rom(
                platform=platform,
                scan_type=ScanType.COMPLETE,
                rom=rom,
                fs_rom={
                    "fs_name": FS_NAME,
                    "flat": True,
                    "nested": False,
                    "files": [],
                    "crc_hash": "",
                    "md5_hash": "",
                    "sha1_hash": "",
                    "ra_hash": "",
                },
                metadata_sources=sources,
                newly_added=False,
            )

    return db_rom_handler.add_rom(scanned)


async def test_a_searched_source_that_misses_drops_its_stale_id():
    saved = await _complete_rescan([MetadataSource.IGDB])

    assert saved.igdb_id is None
    assert saved.igdb_metadata == {}


async def test_a_searched_source_that_matches_stores_the_new_id():
    saved = await _complete_rescan([MetadataSource.IGDB], igdb_result=MATCH)

    assert saved.igdb_id == 9999


async def test_a_source_the_platform_cannot_use_keeps_its_id():
    """No `platform.igdb_id` means IGDB never ran, so it rules nothing out."""
    saved = await _complete_rescan([MetadataSource.IGDB], platform_igdb_id=None)

    assert saved.igdb_id == STALE_IGDB_ID


async def test_a_source_that_fails_keeps_its_id():
    saved = await _complete_rescan(
        [MetadataSource.IGDB], igdb_result=RuntimeError("IGDB is down")
    )

    assert saved.igdb_id == STALE_IGDB_ID


async def test_a_source_that_could_not_be_reached_keeps_its_id():
    """Pouët reports an outage as an empty match, so the handler has to raise."""
    saved = await _complete_rescan(
        [MetadataSource.IGDB, MetadataSource.POUET], pouet_result=UNREACHABLE
    )

    assert saved.pouet_id == STALE_POUET_ID


async def test_a_screenscraper_breaker_keeps_its_id():
    """An exhausted quota answers empty for every remaining ROM."""
    saved = await _complete_rescan(
        [MetadataSource.IGDB, MetadataSource.SS], ss_breaker_tripped=True
    )

    assert saved.ss_id == STALE_SS_ID


async def test_a_selected_screenscraper_that_misses_still_drops_its_id():
    saved = await _complete_rescan([MetadataSource.IGDB, MetadataSource.SS])

    assert saved.ss_id is None


async def test_a_deselected_source_still_drops_its_id():
    saved = await _complete_rescan([MetadataSource.IGDB])

    assert saved.moby_id is None


async def test_steamgriddb_drops_its_stale_id_after_a_miss():
    """SteamGridDB resolves after the reset, so it clears its own ID."""
    saved = await _complete_rescan(
        [MetadataSource.IGDB, MetadataSource.SGDB], igdb_result=MATCH
    )

    assert saved.sgdb_id is None


async def test_steamgriddb_keeps_its_stale_id_when_it_could_not_be_reached():
    saved = await _complete_rescan(
        [MetadataSource.IGDB, MetadataSource.SGDB],
        igdb_result=MATCH,
        sgdb_result=UNREACHABLE,
    )

    assert saved.sgdb_id == STALE_SGDB_ID


@pytest.mark.parametrize(
    "scan_type", [ScanType.QUICK, ScanType.UPDATE, ScanType.UNMATCHED]
)
async def test_only_a_complete_rescan_drops_ids(scan_type: ScanType):
    """Every other scan type carries the existing IDs forward untouched."""
    platform = db_platform_handler.add_platform(
        Platform(id=1, slug="n64", fs_slug="n64", name="Nintendo 64", igdb_id=4)
    )
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            fs_name=FS_NAME,
            fs_name_no_tags="Some Homebrew Thing",
            fs_name_no_ext="Some Homebrew Thing (Aftermarket)",
            fs_extension="z64",
            fs_path="n64",
            name="Wrong Match",
            igdb_id=STALE_IGDB_ID,
            fs_size_bytes=1024,
            tags=[],
        )
    )
    with (
        patch(
            "handler.scan_handler.meta_igdb_handler.get_rom",
            new=AsyncMock(return_value=MISS),
        ),
        patch(
            "handler.scan_handler.meta_igdb_handler.get_rom_by_id",
            new=AsyncMock(return_value=MISS),
        ),
    ):
        async with initialize_context():
            scanned = await scan_rom(
                platform=platform,
                scan_type=scan_type,
                rom=rom,
                fs_rom={
                    "fs_name": FS_NAME,
                    "flat": True,
                    "nested": False,
                    "files": [],
                    "crc_hash": "",
                    "md5_hash": "",
                    "sha1_hash": "",
                    "ra_hash": "",
                },
                metadata_sources=[MetadataSource.IGDB],
                newly_added=False,
            )

    assert db_rom_handler.add_rom(scanned).igdb_id == STALE_IGDB_ID
