"""How a refresh sets a ROM's base fields when it consults only some of its sources."""

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from tests.handler.scan_stubs import add_n64_platform, add_rom, run_scan

from handler.metadata.hasheous_handler import HasheousMetadata, HasheousRom
from handler.metadata.hltb_handler import HLTBMetadata, HLTBRom
from handler.metadata.igdb_handler import IGDBMetadata
from handler.metadata.launchbox_handler.types import LaunchboxMetadata, LaunchboxRom
from handler.scan.sources import MetadataSource, ScanType
from models.rom import Rom

FS_NAME = "Mario Kart 64 (USA).z64"
TITLE = "Mario Kart 64"
HLTB_TITLE = "Mario Kart 8"
LAUNCHBOX_BLOB = {"first_release_date": 851990400}
HLTB_BLOB = {"main_story": 150000}
LAUNCHBOX_COVER = "https://images.launchbox-app.com/mk64-cover.png"
LAUNCHBOX_SHOTS = ["https://images.launchbox-app.com/mk64-shot.png"]
HLTB_COVER = "https://howlongtobeat.com/games/mk8.jpg"

LAUNCHBOX = LaunchboxRom(
    launchbox_id=266,
    name=TITLE,
    url_cover=LAUNCHBOX_COVER,
    url_screenshots=LAUNCHBOX_SHOTS,
    launchbox_metadata=cast(LaunchboxMetadata, LAUNCHBOX_BLOB),
)
HLTB_GUESS = HLTBRom(
    hltb_id=9999,
    name=HLTB_TITLE,
    url_cover=HLTB_COVER,
    hltb_metadata=cast(HLTBMetadata, HLTB_BLOB),
)
HASHEOUS_HIT = HasheousRom(
    hasheous_id=77,
    name=TITLE,
    igdb_id=1234,
    tgdb_id=None,
    hasheous_metadata=cast(HasheousMetadata, {"tosec_match": True}),
)


@pytest.fixture
def lookups() -> Iterator[SimpleNamespace]:
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


@pytest.mark.parametrize(
    "launchbox_metadata",
    [
        pytest.param(
            {**LAUNCHBOX_BLOB, "scan_claims": {"name": TITLE}}, id="title-kept"
        ),
        # A source whose title isn't on record may outrank the newcomer.
        pytest.param(LAUNCHBOX_BLOB, id="stored-before-titles-were-kept"),
    ],
)
async def test_a_lower_ranked_source_does_not_rename_a_game(
    lookups, launchbox_metadata
):
    result = await _scan(
        TITLE,
        ScanType.UNMATCHED,
        [MetadataSource.HLTB],
        launchbox_id=266,
        launchbox_metadata=launchbox_metadata,
    )

    assert result.hltb_id == 9999
    assert result.name == TITLE


async def test_a_higher_ranked_source_replaces_a_lower_ranked_title(lookups):
    """The order is the other way round: HowLongToBeat named it first."""
    result = await _scan(
        HLTB_TITLE,
        ScanType.UNMATCHED,
        [MetadataSource.LAUNCHBOX],
        hltb_id=9999,
        hltb_metadata={**HLTB_BLOB, "scan_claims": {"name": HLTB_TITLE}},
    )

    assert result.launchbox_id == 266
    assert result.name == TITLE


@pytest.mark.parametrize(
    "hltb_metadata",
    [
        pytest.param(
            {**HLTB_BLOB, "scan_claims": {"name": HLTB_TITLE}}, id="title-kept"
        ),
        pytest.param(HLTB_BLOB, id="stored-before-titles-were-kept"),
    ],
)
async def test_an_update_settles_on_the_higher_ranked_title(lookups, hltb_metadata):
    result = await _scan(
        HLTB_TITLE,
        ScanType.UPDATE,
        [MetadataSource.LAUNCHBOX, MetadataSource.HLTB],
        launchbox_id=266,
        launchbox_metadata=LAUNCHBOX_BLOB,
        hltb_id=9999,
        hltb_metadata=hltb_metadata,
    )

    assert result.name == TITLE


async def test_each_answering_source_keeps_its_title(lookups):
    result = await _scan(TITLE, ScanType.UNMATCHED, [MetadataSource.HLTB])

    assert result.hltb_metadata is not None
    assert result.hltb_metadata["scan_claims"] == {
        "name": HLTB_TITLE,
        "url_cover": HLTB_COVER,
    }


async def test_a_name_the_user_typed_is_kept(lookups):
    result = await _scan(
        "MK64",
        ScanType.UPDATE,
        [MetadataSource.LAUNCHBOX, MetadataSource.HLTB],
        launchbox_id=266,
        launchbox_metadata={**LAUNCHBOX_BLOB, "scan_claims": {"name": TITLE}},
        hltb_id=9999,
        hltb_metadata={**HLTB_BLOB, "scan_claims": {"name": HLTB_TITLE}},
    )

    assert result.name == "MK64"


async def test_a_lone_source_still_replaces_the_placeholder(lookups):
    result = await _scan(FS_NAME, ScanType.UNMATCHED, [MetadataSource.HLTB])

    assert result.name == HLTB_TITLE


async def test_a_match_without_metadata_gets_no_blob(lookups):
    """An unmatched scan retries a source whose blob is empty, so none is made."""
    lookups.hltb_by_name.return_value = HLTBRom(hltb_id=9999, name=HLTB_TITLE)
    result = await _scan(TITLE, ScanType.UNMATCHED, [MetadataSource.HLTB])

    assert not result.hltb_metadata


async def _scan_hasheous(igdb_game: HasheousRom) -> Rom:
    """An unmatched Hasheous-only scan, where Hasheous fills IGDB's columns."""
    platform = add_n64_platform(hasheous_id=64)
    rom = add_rom(platform, "mk64 (USA).z64", "mk64")
    with (
        patch(
            "handler.scan.lookups.meta_hasheous_handler.is_enabled", return_value=True
        ),
        patch(
            "handler.scan.lookups.meta_hasheous_handler.lookup_rom",
            new=AsyncMock(return_value=(HASHEOUS_HIT, True)),
        ),
        patch(
            "handler.scan.lookups.meta_hasheous_handler.get_igdb_game",
            new=AsyncMock(return_value=igdb_game),
        ),
    ):
        return await run_scan(
            platform,
            rom,
            scan_type=ScanType.UNMATCHED,
            metadata_sources=[MetadataSource.HASHEOUS],
        )


async def test_an_igdb_id_hasheous_gives_doesnt_hold_the_placeholder():
    result = await _scan_hasheous(HASHEOUS_HIT)

    assert result.igdb_id == 1234
    assert result.name == TITLE


async def test_igdb_metadata_hasheous_gives_keeps_its_title():
    igdb_metadata = cast(IGDBMetadata, {"total_rating": "90"})
    result = await _scan_hasheous(
        HasheousRom({**HASHEOUS_HIT, "igdb_metadata": igdb_metadata})
    )

    assert result.name == TITLE
    assert result.igdb_metadata is not None
    assert result.igdb_metadata["scan_claims"]["name"] == TITLE


async def test_a_hand_edited_title_that_isnt_text_is_ignored(lookups):
    """The raw metadata editor stores any JSON, so a title may not be a string."""
    result = await _scan(
        TITLE,
        ScanType.UNMATCHED,
        [MetadataSource.HLTB],
        launchbox_id=266,
        launchbox_metadata={**LAUNCHBOX_BLOB, "scan_claims": {"name": ["Mario"]}},
    )

    assert result.name == TITLE


async def test_a_lower_ranked_source_does_not_replace_the_artwork(lookups):
    result = await _scan(
        TITLE,
        ScanType.UNMATCHED,
        [MetadataSource.HLTB],
        url_cover=LAUNCHBOX_COVER,
        url_screenshots=LAUNCHBOX_SHOTS,
        launchbox_id=266,
        launchbox_metadata={
            **LAUNCHBOX_BLOB,
            "scan_claims": {
                "name": TITLE,
                "url_cover": LAUNCHBOX_COVER,
                "url_screenshots": LAUNCHBOX_SHOTS,
            },
        },
    )

    assert result.hltb_id == 9999
    assert result.url_cover == LAUNCHBOX_COVER
    assert result.url_screenshots == LAUNCHBOX_SHOTS


async def test_a_higher_ranked_source_replaces_a_lower_ranked_cover(lookups):
    result = await _scan(
        HLTB_TITLE,
        ScanType.UNMATCHED,
        [MetadataSource.LAUNCHBOX],
        url_cover=HLTB_COVER,
        hltb_id=9999,
        hltb_metadata={
            **HLTB_BLOB,
            "scan_claims": {"name": HLTB_TITLE, "url_cover": HLTB_COVER},
        },
    )

    assert result.url_cover == LAUNCHBOX_COVER
    assert result.url_screenshots == LAUNCHBOX_SHOTS


async def test_a_lower_ranked_source_fills_artwork_the_higher_one_lacks(lookups):
    result = await _scan(
        TITLE,
        ScanType.UNMATCHED,
        [MetadataSource.HLTB],
        launchbox_id=266,
        launchbox_metadata={**LAUNCHBOX_BLOB, "scan_claims": {"name": TITLE}},
    )

    assert result.name == TITLE
    assert result.url_cover == HLTB_COVER


async def test_a_match_without_claims_on_record_holds_only_a_stored_value(lookups):
    """An older match keeps the stored cover, but an empty slot still fills."""
    result = await _scan(
        TITLE,
        ScanType.UNMATCHED,
        [MetadataSource.HLTB],
        url_cover="",
        launchbox_id=266,
        launchbox_metadata=LAUNCHBOX_BLOB,
    )

    assert result.name == TITLE
    assert result.url_cover == HLTB_COVER
