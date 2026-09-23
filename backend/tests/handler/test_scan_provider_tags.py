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
SS_TRANSLATED = SSRom(ss_id=42, name="Mario Kart 64", tags=["Translation"])


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
def ss_translated() -> Iterator[AsyncMock]:
    """Patch a hash lookup whose dump carries ScreenScraper's `trad` flag."""
    with patch(
        "handler.scan_handler.meta_ss_handler.lookup_rom",
        new=AsyncMock(return_value=(SS_TRANSLATED, False)),
    ) as by_hash:
        yield by_hash


@pytest.fixture
def ss_translated_by_id() -> Iterator[AsyncMock]:
    """Patch the id refetch an UPDATE scan takes, dump tags included."""
    with patch(
        "handler.scan_handler.meta_ss_handler.get_rom_by_id",
        new=AsyncMock(return_value=SS_TRANSLATED),
    ) as by_id:
        yield by_id


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
    scan_type: ScanType = ScanType.COMPLETE,
    **rom_overrides: Any,
) -> Rom:
    platform = add_n64_platform(hasheous_id=4, ss_id=14)
    rom = add_rom(platform, fs_name, "Mario Kart 64", **rom_overrides)

    return await run_scan(platform, rom, scan_type=scan_type, metadata_sources=[source])


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


async def test_screenscraper_tags_a_translated_dump(ss_translated: AsyncMock):
    result = await _scan(MetadataSource.SS, tags=[])

    assert result.tags == ["Translation"]


async def test_a_dump_tag_joins_the_filename_tags(ss_translated: AsyncMock):
    """Unlike a region, a tag adds: the dump is a translation and a beta."""
    result = await _scan(MetadataSource.SS, fs_name="Mario Kart 64 (Japan) (Beta).z64")

    assert result.tags == ["Beta", "Translation"]


async def test_a_tag_both_sources_report_is_not_repeated(ss_translated: AsyncMock):
    result = await _scan(
        MetadataSource.SS,
        fs_name="Mario Kart 64 (Japan) [T+Eng].z64",
    )

    assert result.tags == ["Translation"]


async def test_an_update_rescan_keeps_the_dump_tag(ss_translated_by_id: AsyncMock):
    """An UPDATE refetches by id, which still carries the game's dumps."""
    result = await _scan(
        MetadataSource.SS,
        scan_type=ScanType.UPDATE,
        ss_id=42,
    )

    assert result.tags == ["Translation"]

    # The files are what let the refetch pick our dump out of the game's.
    await_args = ss_translated_by_id.await_args
    assert await_args is not None, "the id path should run"
    assert len(await_args.args) == 3, "the refetch needs the files"


async def test_a_dump_that_is_no_longer_a_translation_loses_the_tag(
    ss_lookup: AsyncMock,
):
    """The row cannot say where a tag came from, so it is never the base."""
    result = await _scan(MetadataSource.SS, tags=["Translation"])

    assert result.tags == []


async def test_a_filename_tag_survives_a_provider_that_reports_none(
    ss_lookup: AsyncMock,
):
    result = await _scan(MetadataSource.SS, fs_name="Mario Kart 64 (Beta).z64")

    assert result.tags == ["Beta"]


async def test_a_dump_tag_is_kept_in_its_sources_blob(ss_translated: AsyncMock):
    result = await _scan(MetadataSource.SS)

    assert result.ss_metadata is not None
    assert result.ss_metadata["dump_tags"] == ["Translation"]


async def test_an_update_that_skips_screenscraper_keeps_what_its_dump_said():
    """The row's tags are re-read from the filename first, as a selected rescan does."""
    result = await _scan(
        MetadataSource.HASHEOUS,
        scan_type=ScanType.UPDATE,
        ss_id=42,
        ss_metadata={"dump_regions": ["Europe"], "dump_tags": ["Translation"]},
        regions=[],
        tags=[],
    )

    assert result.regions == ["Europe"]
    assert result.tags == ["Translation"]


async def test_a_hashes_scan_keeps_the_dump_tag_screenscraper_gave():
    """A hashes scan never asks ScreenScraper again, and tags merge onto the filename's."""
    result = await _scan(
        MetadataSource.SS,
        scan_type=ScanType.HASHES,
        ss_id=42,
        ss_metadata={"dump_tags": ["Translation"]},
        tags=["Translation"],
    )

    assert result.tags == ["Translation"]


async def test_a_fresh_answer_replaces_what_the_blob_kept():
    """ScreenScraper answering without our dump outranks the dump tags it kept."""
    with patch(
        "handler.scan_handler.meta_ss_handler.get_rom_by_id",
        new=AsyncMock(return_value=SS_MATCH),
    ):
        result = await _scan(
            MetadataSource.SS,
            scan_type=ScanType.UPDATE,
            ss_id=42,
            ss_metadata={"dump_tags": ["Translation"]},
            tags=[],
        )

    assert result.tags == []
    assert result.ss_metadata is not None
    assert "dump_tags" not in result.ss_metadata


async def test_a_complete_rescan_without_screenscraper_drops_its_tags(
    hasheous_lookup: AsyncMock,
):
    result = await _scan(
        MetadataSource.HASHEOUS,
        ss_id=42,
        ss_metadata={"dump_tags": ["Translation"]},
        tags=["Translation"],
    )

    assert result.tags == []
