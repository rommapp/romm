"""How a scan applies the regions and languages a hash-matched provider reports.

A hash names one dump, so its tags fill a gap the filename left, never overwrite it.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from tests.handler.scan_stubs import add_n64_platform, add_rom, run_scan

from handler.metadata.hasheous_handler import HasheousRom
from handler.metadata.ss_handler import SSRom
from handler.scan_handler import MetadataSource, ScanType
from models.rom import Rom

HASHEOUS_MATCH = HasheousRom(
    hasheous_id=1,
    name="Mario Kart 64",
    igdb_id=None,
    tgdb_id=None,
    ra_id=None,
    regions=["Japan"],
    languages=["Japanese"],
)
SS_MATCH = SSRom(ss_id=42, name="Mario Kart 64", regions=["Europe"])


@pytest.fixture
def hasheous_lookup() -> Iterator[AsyncMock]:
    """Patch the Hasheous hash lookup and the two proxied catalog fetches."""
    with (
        patch(
            "handler.scan_handler.meta_hasheous_handler.lookup_rom",
            new=AsyncMock(return_value=(HASHEOUS_MATCH, True)),
        ) as lookup,
        patch(
            "handler.scan_handler.meta_hasheous_handler.get_igdb_game",
            new=AsyncMock(return_value=HasheousRom(hasheous_id=1)),
        ),
        patch(
            "handler.scan_handler.meta_hasheous_handler.get_ra_game",
            new=AsyncMock(return_value=HasheousRom(hasheous_id=1)),
        ),
    ):
        yield lookup


@pytest.fixture
def ss_lookup() -> Iterator[AsyncMock]:
    """Patch the ScreenScraper hash lookup, the only one that names a dump."""
    with patch(
        "handler.scan_handler.meta_ss_handler.lookup_rom",
        new=AsyncMock(return_value=(SS_MATCH, False)),
    ) as by_hash:
        yield by_hash


@pytest.fixture
def ss_name_search() -> Iterator[AsyncMock]:
    """Patch the ScreenScraper name search, which identifies a title, not a dump."""
    with (
        patch(
            "handler.scan_handler.meta_ss_handler.lookup_rom",
            new=AsyncMock(return_value=(SSRom(ss_id=None), False)),
        ),
        patch(
            "handler.scan_handler.meta_ss_handler.get_rom",
            new=AsyncMock(return_value=SSRom(ss_id=42, name="Mario Kart 64")),
        ) as by_name,
    ):
        yield by_name


async def _scan(
    source: MetadataSource,
    fs_name: str = "Mario Kart 64.z64",
    **rom_overrides: Any,
) -> Rom:
    platform = add_n64_platform(hasheous_id=4, ss_id=14)
    rom = add_rom(platform, fs_name, "Mario Kart 64", **rom_overrides)

    return await run_scan(
        platform, rom, scan_type=ScanType.COMPLETE, metadata_sources=[source]
    )


async def test_hasheous_fills_untagged_regions_and_languages(
    hasheous_lookup: AsyncMock,
):
    result = await _scan(MetadataSource.HASHEOUS, regions=[], languages=[])

    assert result.regions == ["Japan"]
    assert result.languages == ["Japanese"]


async def test_hasheous_leaves_the_filename_tags_alone(hasheous_lookup: AsyncMock):
    result = await _scan(
        MetadataSource.HASHEOUS,
        fs_name="Mario Kart 64 (USA) (En).z64",
        regions=["USA"],
        languages=["English"],
    )

    assert result.regions == ["USA"]
    assert result.languages == ["English"]


async def test_screenscraper_fills_untagged_regions(ss_lookup: AsyncMock):
    result = await _scan(MetadataSource.SS, regions=[])

    assert result.regions == ["Europe"]


async def test_screenscraper_leaves_the_filename_tags_alone(ss_lookup: AsyncMock):
    result = await _scan(
        MetadataSource.SS, fs_name="Mario Kart 64 (Japan).z64", regions=["Japan"]
    )

    assert result.regions == ["Japan"]


async def test_a_screenscraper_name_match_reports_no_regions(ss_name_search: AsyncMock):
    """A title matched by name says nothing about which dump is on disk."""
    result = await _scan(MetadataSource.SS, regions=[])

    assert result.ss_id == 42
    assert result.regions == []


async def test_a_tag_an_earlier_scan_stored_is_refreshed(hasheous_lookup: AsyncMock):
    """The filename owns the slot, not whatever a provider left on the row."""
    result = await _scan(
        MetadataSource.HASHEOUS, regions=["Europe"], languages=["French"]
    )

    assert result.regions == ["Japan"]
    assert result.languages == ["Japanese"]
