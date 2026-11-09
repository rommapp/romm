"""How a refresh names a ROM when it consults only some of the ROM's sources.

`scan.priority.metadata` ranks the sources for the title. An unmatched scan asks
only the sources a ROM lacks, so its own pick would follow the order the scans
ran in: LaunchBox's "Mario Kart 64", then an unmatched HowLongToBeat scan that
guesses "Mario Kart 8", would leave the lower-ranked guess as the name.
"""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from tests.handler.scan_stubs import add_n64_platform, add_rom, run_scan

from handler.metadata.hltb_handler import HLTBMetadata, HLTBRom
from handler.metadata.launchbox_handler.types import LaunchboxMetadata, LaunchboxRom
from handler.scan.sources import MetadataSource, ScanType
from models.rom import Rom

FS_NAME = "Mario Kart 64 (USA).z64"
TITLE = "Mario Kart 64"

LAUNCHBOX = LaunchboxRom(
    launchbox_id=266,
    name="Mario Kart 64",
    launchbox_metadata=cast(LaunchboxMetadata, {"first_release_date": 851990400}),
)
HLTB_GUESS = HLTBRom(
    hltb_id=9999,
    name="Mario Kart 8",
    hltb_metadata=HLTBMetadata(main_story=150000),
)


@pytest.fixture
def lookups() -> Iterator[SimpleNamespace]:
    """Patch the LaunchBox and HowLongToBeat lookups."""
    with (
        patch(
            "handler.scan.lookups.resolve_launchbox_rom",
            new=AsyncMock(return_value=LAUNCHBOX),
        ) as launchbox,
        patch(
            "handler.scan.lookups.meta_hltb_handler.get_rom",
            new=AsyncMock(return_value=HLTB_GUESS),
        ) as hltb_by_name,
        patch(
            "handler.scan.lookups.meta_hltb_handler.get_rom_by_id",
            new=AsyncMock(return_value=HLTB_GUESS),
        ),
    ):
        yield SimpleNamespace(launchbox=launchbox, hltb_by_name=hltb_by_name)


async def _scan(
    name: str, scan_type: ScanType, sources: list[str], **stored: Any
) -> Rom:
    platform = add_n64_platform()
    rom = add_rom(platform, FS_NAME, name, fs_name_no_tags=TITLE, **stored)
    return await run_scan(platform, rom, scan_type=scan_type, metadata_sources=sources)


async def test_a_lower_ranked_source_does_not_rename_a_game(lookups):
    result = await _scan(
        TITLE,
        ScanType.UNMATCHED,
        [MetadataSource.HLTB],
        launchbox_id=266,
        launchbox_metadata={"first_release_date": 851990400, "name": "Mario Kart 64"},
    )

    assert result.hltb_id == 9999
    assert result.name == "Mario Kart 64"


async def test_a_match_stored_before_titles_were_kept_holds_the_name(lookups):
    """A source whose title isn't on record may outrank the newcomer."""
    result = await _scan(
        TITLE,
        ScanType.UNMATCHED,
        [MetadataSource.HLTB],
        launchbox_id=266,
        launchbox_metadata={"first_release_date": 851990400},
    )

    assert result.name == "Mario Kart 64"


async def test_a_higher_ranked_source_replaces_a_lower_ranked_title(lookups):
    """The order is the other way round: HowLongToBeat named it first."""
    result = await _scan(
        "Mario Kart 8",
        ScanType.UNMATCHED,
        [MetadataSource.LAUNCHBOX],
        hltb_id=9999,
        hltb_metadata={"main_story": 150000, "name": "Mario Kart 8"},
    )

    assert result.launchbox_id == 266
    assert result.name == "Mario Kart 64"


async def test_an_update_settles_on_the_higher_ranked_title(lookups):
    result = await _scan(
        "Mario Kart 8",
        ScanType.UPDATE,
        [MetadataSource.LAUNCHBOX, MetadataSource.HLTB],
        launchbox_id=266,
        launchbox_metadata={"first_release_date": 851990400},
        hltb_id=9999,
        hltb_metadata={"main_story": 150000, "name": "Mario Kart 8"},
    )

    assert result.name == "Mario Kart 64"


async def test_each_answering_source_keeps_its_title(lookups):
    result = await _scan(TITLE, ScanType.UNMATCHED, [MetadataSource.HLTB])

    assert result.hltb_metadata is not None
    assert result.hltb_metadata["name"] == "Mario Kart 8"


async def test_a_name_the_user_typed_is_kept(lookups):
    result = await _scan(
        "MK64",
        ScanType.UPDATE,
        [MetadataSource.LAUNCHBOX, MetadataSource.HLTB],
        launchbox_id=266,
        launchbox_metadata={"first_release_date": 851990400, "name": "Mario Kart 64"},
        hltb_id=9999,
        hltb_metadata={"main_story": 150000, "name": "Mario Kart 8"},
    )

    assert result.name == "MK64"


async def test_a_lone_source_still_replaces_the_placeholder(lookups):
    result = await _scan(FS_NAME, ScanType.UNMATCHED, [MetadataSource.HLTB])

    assert result.name == "Mario Kart 8"


async def test_a_match_without_metadata_gets_no_blob(lookups):
    """An unmatched scan retries a source whose blob is empty, so none is made."""
    lookups.hltb_by_name.return_value = HLTBRom(hltb_id=9999, name="Mario Kart 8")
    result = await _scan(TITLE, ScanType.UNMATCHED, [MetadataSource.HLTB])

    assert not result.hltb_metadata
