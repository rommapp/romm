"""How a scan picks a ROM's HowLongToBeat match.

The filename lookup matches fuzzily, so re-running it on a ROM that already
carries an ID lets a different game outscore a match the user pinned by hand.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from tests.handler.scan_stubs import add_n64_platform, add_rom, run_scan

from handler.metadata.hltb_handler import HLTBMetadata, HLTBRom
from handler.scan_handler import MetadataSource, ScanType
from models.rom import Rom

FS_NAME = "Mario Kart 64 (USA).z64"
PINNED = HLTBRom(hltb_id=2255, name="Mario Kart 64")
GUESSED = HLTBRom(hltb_id=9999, name="Mario Kart 8")
NO_MATCH = HLTBRom(hltb_id=None)


@pytest.fixture
def lookups():
    """Patch both HowLongToBeat lookups, defaulting each to a miss."""
    with (
        patch(
            "handler.scan_handler.meta_hltb_handler.get_rom_by_id",
            new=AsyncMock(return_value=NO_MATCH),
        ) as by_id,
        patch(
            "handler.scan_handler.meta_hltb_handler.get_rom",
            new=AsyncMock(return_value=NO_MATCH),
        ) as by_name,
    ):
        yield SimpleNamespace(by_id=by_id, by_name=by_name)


async def _scan(
    scan_type: ScanType,
    hltb_id: int | None = None,
    hltb_metadata: HLTBMetadata | None = None,
) -> Rom:
    platform = add_n64_platform()
    rom = add_rom(
        platform,
        FS_NAME,
        "Mario Kart 64",
        hltb_id=hltb_id,
        hltb_metadata=dict(hltb_metadata or {}),
    )

    return await run_scan(
        platform, rom, scan_type=scan_type, metadata_sources=[MetadataSource.HLTB]
    )


async def test_no_stored_id_uses_the_file_name_lookup(lookups):
    lookups.by_name.return_value = GUESSED

    result = await _scan(ScanType.COMPLETE)

    lookups.by_id.assert_not_awaited()
    lookups.by_name.assert_awaited_once_with(FS_NAME, "n64")
    assert result.hltb_id == 9999


async def test_complete_rescan_rematches_a_stored_id(lookups):
    """A complete rescan wipes external IDs by design, so it re-runs the search."""
    lookups.by_name.return_value = GUESSED

    result = await _scan(ScanType.COMPLETE, hltb_id=2255)

    lookups.by_id.assert_not_awaited()
    lookups.by_name.assert_awaited_once_with(FS_NAME, "n64")
    assert result.hltb_id == 9999


async def test_update_scan_refetches_a_stored_id(lookups):
    """A pinned match is refreshed by ID, never re-guessed from the filename."""
    lookups.by_id.return_value = PINNED

    result = await _scan(
        ScanType.UPDATE, hltb_id=2255, hltb_metadata=HLTBMetadata(release_year=1997)
    )

    lookups.by_id.assert_awaited_once_with(2255)
    lookups.by_name.assert_not_awaited()
    assert result.hltb_id == 2255


async def test_stored_id_is_not_replaced_by_a_file_name_guess(lookups):
    """An ID the provider can't resolve stays put rather than being re-guessed."""
    await _scan(ScanType.UPDATE, hltb_id=2255)

    lookups.by_id.assert_awaited_once_with(2255)
    lookups.by_name.assert_not_awaited()


async def test_unmatched_scan_refetches_metadata_for_a_stored_id(lookups):
    lookups.by_id.return_value = PINNED

    result = await _scan(ScanType.UNMATCHED, hltb_id=2255)

    lookups.by_id.assert_awaited_once_with(2255)
    lookups.by_name.assert_not_awaited()
    assert result.hltb_id == 2255


async def test_unmatched_scan_without_a_stored_id_uses_the_file_name_lookup(lookups):
    lookups.by_name.return_value = GUESSED

    await _scan(ScanType.UNMATCHED)

    lookups.by_id.assert_not_awaited()
    lookups.by_name.assert_awaited_once_with(FS_NAME, "n64")
