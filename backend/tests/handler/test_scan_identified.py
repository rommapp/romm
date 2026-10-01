"""Which provider matches count as an identified ROM during a scan.

A scan that finds no match returns early and skips the SteamGridDB lookup, so
every source `Rom.is_identified` counts must keep the scan going.
"""

from unittest.mock import AsyncMock, patch

import pytest
from tests.handler.scan_stubs import add_n64_platform, add_rom, run_scan

from handler.metadata.libretro_handler import LibretroRom
from handler.metadata.sgdb_handler import SGDBRom
from handler.scan_handler import MetadataSource, ScanType

FS_NAME = "Mario Kart 64 (USA).z64"


@pytest.fixture
def sgdb_lookup():
    with patch(
        "handler.scan_handler.meta_sgdb_handler.get_details_by_names",
        new=AsyncMock(return_value=SGDBRom(sgdb_id=None)),
    ) as lookup:
        yield lookup


async def test_libretro_only_match_counts_as_identified(sgdb_lookup):
    platform = add_n64_platform()
    rom = add_rom(platform, FS_NAME, "Mario Kart 64")

    with patch(
        "handler.scan_handler.meta_libretro_handler.get_rom",
        new=AsyncMock(
            return_value=LibretroRom(
                libretro_id="Mario Kart 64 (USA)", name="Mario Kart 64"
            )
        ),
    ):
        result = await run_scan(
            platform,
            rom,
            scan_type=ScanType.COMPLETE,
            metadata_sources=[MetadataSource.LIBRETRO, MetadataSource.SGDB],
        )

    assert result.libretro_id == "Mario Kart 64 (USA)"
    assert result.is_identified
    assert result.missing_from_fs is False
    sgdb_lookup.assert_awaited_once()


async def test_unmatched_rom_skips_the_sgdb_lookup(sgdb_lookup):
    platform = add_n64_platform()
    rom = add_rom(platform, FS_NAME, "Mario Kart 64")

    with patch(
        "handler.scan_handler.meta_libretro_handler.get_rom",
        new=AsyncMock(return_value=LibretroRom(libretro_id=None)),
    ):
        result = await run_scan(
            platform,
            rom,
            scan_type=ScanType.COMPLETE,
            metadata_sources=[MetadataSource.LIBRETRO, MetadataSource.SGDB],
        )

    assert not result.is_identified
    sgdb_lookup.assert_not_awaited()
