"""When a scan asks Playmatch, whose ids only feed the other sources."""

from typing import Any
from unittest.mock import AsyncMock, patch

from tests.handler.scan_stubs import add_n64_platform, add_rom, run_scan

from handler.metadata import meta_igdb_handler, meta_playmatch_handler
from handler.metadata.igdb_handler import IGDBRom
from handler.scan_handler import MetadataSource, ScanType


async def _update_scan(**rom_fields: Any) -> AsyncMock:
    platform = add_n64_platform(igdb_id=4)
    rom = add_rom(platform, "Paper Mario (USA).z64", "Paper Mario", **rom_fields)
    lookup = AsyncMock(wraps=meta_playmatch_handler.lookup_rom)

    with (
        patch.object(meta_playmatch_handler, "is_enabled", return_value=True),
        patch.object(meta_playmatch_handler, "lookup_rom", new=lookup),
        patch.object(
            meta_igdb_handler,
            "get_rom_by_id",
            new=AsyncMock(return_value=IGDBRom(igdb_id=None)),
        ),
    ):
        await run_scan(
            platform,
            rom,
            scan_type=ScanType.UPDATE,
            metadata_sources=[MetadataSource.PLAYMATCH, MetadataSource.IGDB],
        )
    return lookup


async def test_an_update_asks_playmatch_for_a_source_it_refreshes():
    lookup = await _update_scan(igdb_id=1)

    lookup.assert_awaited_once()


async def test_an_update_skips_playmatch_when_no_source_it_feeds_runs():
    lookup = await _update_scan()

    lookup.assert_not_awaited()
