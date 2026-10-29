from typing import Any
from unittest.mock import patch

import pytest

from handler.metadata.flashpoint_handler import FLASHPOINT_PLATFORM_LIST
from handler.metadata.hltb_handler import HLTB_PLATFORM_LIST
from handler.metadata.libretro_handler import LIBRETRO_PLATFORM_LIST
from handler.metadata.steam_handler import STEAM_PLATFORMS
from handler.scan_handler import (
    RESCAN_RULES,
    MetadataSource,
    ScanType,
    should_consult,
)
from models.platform import Platform
from models.rom import Rom

# A slug each slug-gated source covers; every other source keys off a platform id.
COVERED_SLUG = {
    MetadataSource.FLASHPOINT: next(iter(FLASHPOINT_PLATFORM_LIST)),
    MetadataSource.HLTB: next(iter(HLTB_PLATFORM_LIST)),
    MetadataSource.LIBRETRO: next(iter(LIBRETRO_PLATFORM_LIST)),
    MetadataSource.STEAM: next(iter(STEAM_PLATFORMS)),
}


def _platform(source: MetadataSource, slug: str | None = None) -> Platform:
    return Platform(
        slug=slug or COVERED_SLUG.get(source, "n64"),
        igdb_id=4,
        moby_id=9,
        ss_id=14,
        ra_id=2,
        hasheous_id=8,
    )


def _rom(platform: Platform, **fields: Any) -> Rom:
    return Rom(platform=platform, **fields)


def _consults(
    source: MetadataSource,
    scan_type: ScanType,
    rom: Rom,
    *,
    newly_added: bool = False,
    enabled: bool = True,
) -> bool:
    with patch(
        "handler.scan_handler.meta_igdb_handler.get_platform",
        return_value={"igdb_id": 4},
    ):
        return should_consult(
            source,
            scan_type=scan_type,
            rom=rom,
            platform=rom.platform,
            newly_added=newly_added,
            metadata_sources=[source.value] if enabled else [],
        )


ALL_SOURCES = list(RESCAN_RULES)


def test_every_scanned_source_has_a_rule():
    """TheGamesDB is read off Hasheous and Playmatch has its own gate."""
    assert set(RESCAN_RULES) == set(MetadataSource) - {
        MetadataSource.TGDB,
        MetadataSource.PLAYMATCH,
    }


# Written out rather than derived, so a rule pointing at the wrong column fails.
EXPECTED_COLUMNS: dict[MetadataSource, tuple[str, str | None]] = {
    MetadataSource.IGDB: ("igdb_id", "igdb_metadata"),
    MetadataSource.MOBY: ("moby_id", "moby_metadata"),
    MetadataSource.SS: ("ss_id", "ss_metadata"),
    MetadataSource.RA: ("ra_id", "ra_metadata"),
    MetadataSource.LAUNCHBOX: ("launchbox_id", "launchbox_metadata"),
    MetadataSource.HASHEOUS: ("hasheous_id", "hasheous_metadata"),
    MetadataSource.SGDB: ("sgdb_id", None),
    MetadataSource.FLASHPOINT: ("flashpoint_id", "flashpoint_metadata"),
    MetadataSource.HLTB: ("hltb_id", "hltb_metadata"),
    MetadataSource.DEMOZOO: ("demozoo_id", "demozoo_metadata"),
    MetadataSource.POUET: ("pouet_id", "pouet_metadata"),
    MetadataSource.CSDB: ("csdb_id", "csdb_metadata"),
    MetadataSource.STEAM: ("steam_id", "steam_metadata"),
    MetadataSource.GAMELIST: ("gamelist_id", "gamelist_metadata"),
    MetadataSource.LIBRETRO: ("libretro_id", None),
}


@pytest.mark.parametrize("source", ALL_SOURCES)
def test_each_rule_reads_its_own_columns(source: MetadataSource):
    rule = RESCAN_RULES[source]
    assert (rule.id_field, rule.metadata_field) == EXPECTED_COLUMNS[source]


@pytest.mark.parametrize("source", ALL_SOURCES)
def test_a_disabled_source_is_never_consulted(source: MetadataSource):
    rom = _rom(_platform(source))
    assert not _consults(source, ScanType.COMPLETE, rom, enabled=False)


@pytest.mark.parametrize("source", ALL_SOURCES)
@pytest.mark.parametrize("scan_type", list(ScanType))
def test_a_new_rom_consults_every_source(source: MetadataSource, scan_type: ScanType):
    rom = _rom(_platform(source))
    assert _consults(source, scan_type, rom, newly_added=True)


@pytest.mark.parametrize("source", ALL_SOURCES)
def test_a_complete_rescan_consults_a_matched_source(source: MetadataSource):
    rule = RESCAN_RULES[source]
    rom = _rom(_platform(source), **{rule.id_field: 1})
    assert _consults(source, ScanType.COMPLETE, rom)


@pytest.mark.parametrize("source", ALL_SOURCES)
def test_an_update_refreshes_only_a_matched_source(source: MetadataSource):
    rule = RESCAN_RULES[source]
    platform = _platform(source)
    assert _consults(source, ScanType.UPDATE, _rom(platform, **{rule.id_field: 1}))
    assert not _consults(source, ScanType.UPDATE, _rom(platform))


@pytest.mark.parametrize("source", ALL_SOURCES)
def test_an_unmatched_scan_retries_a_missing_match(source: MetadataSource):
    assert _consults(source, ScanType.UNMATCHED, _rom(_platform(source)))


@pytest.mark.parametrize("source", ALL_SOURCES)
def test_an_unmatched_scan_skips_a_full_match(source: MetadataSource):
    rule = RESCAN_RULES[source]
    fields: dict[str, Any] = {rule.id_field: 1}
    if rule.metadata_field:
        fields[rule.metadata_field] = {"name": "Matched"}
    assert not _consults(source, ScanType.UNMATCHED, _rom(_platform(source), **fields))


@pytest.mark.parametrize(
    "source",
    [s for s in ALL_SOURCES if RESCAN_RULES[s].metadata_field is not None],
)
def test_an_unmatched_scan_retries_an_id_without_metadata(source: MetadataSource):
    rule = RESCAN_RULES[source]
    rom = _rom(_platform(source), **{rule.id_field: 1})
    assert _consults(source, ScanType.UNMATCHED, rom)


@pytest.mark.parametrize(
    "source",
    [
        MetadataSource.MOBY,
        MetadataSource.SS,
        MetadataSource.RA,
        MetadataSource.LAUNCHBOX,
        MetadataSource.HASHEOUS,
    ],
)
def test_an_unmatched_scan_skips_a_platform_the_source_does_not_list(
    source: MetadataSource,
):
    rom = _rom(_platform(source, slug="not-a-platform"))
    assert not _consults(source, ScanType.UNMATCHED, rom)
    # Only the unmatched retry checks the list; a complete rescan still asks.
    assert _consults(source, ScanType.COMPLETE, rom)


@pytest.mark.parametrize("source", list(COVERED_SLUG))
def test_a_platform_outside_the_sources_list_is_never_consulted(
    source: MetadataSource,
):
    rom = _rom(_platform(source, slug="not-a-platform"))
    assert not _consults(source, ScanType.COMPLETE, rom, newly_added=True)


@pytest.mark.parametrize(
    "source",
    [
        MetadataSource.IGDB,
        MetadataSource.MOBY,
        MetadataSource.SS,
        MetadataSource.RA,
        MetadataSource.HASHEOUS,
    ],
)
def test_a_platform_without_the_sources_id_is_never_consulted(
    source: MetadataSource,
):
    platform = _platform(source)
    setattr(platform, f"{source.value}_id", None)
    assert not _consults(source, ScanType.COMPLETE, _rom(platform), newly_added=True)


@pytest.mark.parametrize("source", ALL_SOURCES)
def test_a_hash_scan_consults_only_the_hash_sources(source: MetadataSource):
    rule = RESCAN_RULES[source]
    rom = _rom(_platform(source), **{rule.id_field: 1})
    assert _consults(source, ScanType.HASHES, rom) == (
        source in {MetadataSource.RA, MetadataSource.HASHEOUS}
    )


@pytest.mark.parametrize("source", ALL_SOURCES)
@pytest.mark.parametrize("scan_type", [ScanType.QUICK, ScanType.NEW_PLATFORMS])
def test_a_quick_scan_leaves_an_existing_rom_alone(
    source: MetadataSource, scan_type: ScanType
):
    rule = RESCAN_RULES[source]
    rom = _rom(_platform(source), **{rule.id_field: 1})
    assert not _consults(source, scan_type, rom)


def test_an_unmatched_scan_skips_a_platform_igdb_does_not_list():
    rom = _rom(_platform(MetadataSource.IGDB))
    with patch(
        "handler.scan_handler.meta_igdb_handler.get_platform",
        return_value={"igdb_id": None},
    ):
        assert not should_consult(
            MetadataSource.IGDB,
            scan_type=ScanType.UNMATCHED,
            rom=rom,
            platform=rom.platform,
            newly_added=False,
            metadata_sources=[MetadataSource.IGDB.value],
        )
