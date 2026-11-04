"""What a scan asks: the metadata sources, scan types and rescan rules."""

import enum
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Any, Final

from config.config_manager import config_manager as cm
from handler.metadata import (
    meta_csdb_handler,
    meta_demozoo_handler,
    meta_flashpoint_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_libretro_handler,
    meta_moby_handler,
    meta_playmatch_handler,
    meta_pouet_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
    meta_steam_handler,
    meta_tgdb_handler,
)
from handler.metadata.flashpoint_handler import FLASHPOINT_PLATFORM_LIST
from handler.metadata.hasheous_handler import HASHEOUS_PLATFORM_LIST
from handler.metadata.hltb_handler import HLTB_PLATFORM_LIST
from handler.metadata.launchbox_handler.platforms import LAUNCHBOX_PLATFORM_LIST
from handler.metadata.libretro_handler import LIBRETRO_PLATFORM_LIST
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST
from handler.metadata.ra_handler import RA_PLATFORM_LIST
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST
from handler.metadata.steam_handler import STEAM_PLATFORMS
from models.platform import Platform
from models.rom import Rom

LOGGER_MODULE_NAME = {"module_name": "scan"}


@enum.unique
class ScanType(enum.StrEnum):
    NEW_PLATFORMS = "new_platforms"
    QUICK = "quick"
    UPDATE = "update"
    UNMATCHED = "unmatched"
    COMPLETE = "complete"
    HASHES = "hashes"


@enum.unique
class MetadataSource(enum.StrEnum):
    IGDB = "igdb"  # IGDB
    MOBY = "moby"  # MobyGames
    SS = "ss"  # Screenscraper
    RA = "ra"  # RetroAchievements
    LAUNCHBOX = "launchbox"  # Launchbox
    HASHEOUS = "hasheous"  # Hasheous
    TGDB = "tgdb"  # TheGamesDB
    SGDB = "sgdb"  # SteamGridDB
    FLASHPOINT = "flashpoint"  # Flashpoint Project
    HLTB = "hltb"  # HowLongToBeat
    DEMOZOO = "demozoo"  # Demozoo
    POUET = "pouet"  # Pouët
    CSDB = "csdb"  # CSDb (C64)
    STEAM = "steam"  # Steam storefront
    GAMELIST = "gamelist"  # ES-DE gamelist.xml
    LIBRETRO = "libretro"  # Libretro thumbnails
    PLAYMATCH = "playmatch"  # Playmatch


# Demozoo / Pouët identify a production, not a retail game. Game catalogs
# (IGDB, Moby, ScreenScraper, SteamGridDB, …) still run and will happily
# attach a similarly titled box: "Desert Dream" → Desert Fox, "State of
# the Art" → a skate game. Once a scene ID exists, only Demozoo / Pouët /
# CSDb may set name, summary, or artwork. Regular games never have those
# IDs, so they keep the usual fuzzy cover matching.
SCENE_METADATA_SOURCES = frozenset(
    {MetadataSource.DEMOZOO, MetadataSource.POUET, MetadataSource.CSDB}
)


# Sources that report the dump a hash matched rather than the title. Their tags
# fill an empty slot only: a filename and a gamelist.xml are curated with the
# library, so they own these fields and the locale pickers read them back.
HASH_MATCHED_TAG_SOURCES = frozenset({MetadataSource.SS, MetadataSource.HASHEOUS})


PROVIDER_TAG_FIELDS = ("regions", "languages")


# Tags merge rather than fill: being a translation says nothing about being a
# revision, so a dump's tags join the filename's instead of replacing them.
PROVIDER_MERGED_TAG_FIELDS = ("tags",)


PROVIDER_ALL_TAG_FIELDS = PROVIDER_TAG_FIELDS + PROVIDER_MERGED_TAG_FIELDS


# Where a hash source's blob keeps each tag field its dump gave.
DUMP_TAG_KEYS = {field: f"dump_{field}" for field in PROVIDER_ALL_TAG_FIELDS}


def _always(_entity: Any) -> bool:
    return True


@dataclass(frozen=True)
class RescanRule:
    """When a scan consults one metadata source for a rom.

    Args:
        id_field: the rom column holding the source's match id.
        metadata_field: the column an unmatched scan must find filled, or None
            when the id alone counts as a match.
        platform_supported: whether the source covers the platform at all.
        unmatched_supported: an extra platform check an unmatched scan makes.
        on_hashes: whether a hash scan consults the source.
    """

    id_field: str
    metadata_field: str | None
    platform_supported: Callable[[Platform], Any] = _always
    unmatched_supported: Callable[[Platform], Any] = _always
    on_hashes: bool = False


RESCAN_RULES: Final[Mapping[MetadataSource, RescanRule]] = {
    MetadataSource.IGDB: RescanRule(
        "igdb_id",
        "igdb_metadata",
        platform_supported=lambda p: p.igdb_id,
        unmatched_supported=lambda p: meta_igdb_handler.get_platform(p.slug)["igdb_id"],
    ),
    MetadataSource.MOBY: RescanRule(
        "moby_id",
        "moby_metadata",
        platform_supported=lambda p: p.moby_id,
        unmatched_supported=lambda p: p.slug in MOBYGAMES_PLATFORM_LIST,
    ),
    MetadataSource.SS: RescanRule(
        "ss_id",
        "ss_metadata",
        platform_supported=lambda p: p.ss_id,
        unmatched_supported=lambda p: p.slug in SCREENSAVER_PLATFORM_LIST,
    ),
    MetadataSource.RA: RescanRule(
        "ra_id",
        "ra_metadata",
        platform_supported=lambda p: p.ra_id,
        unmatched_supported=lambda p: p.slug in RA_PLATFORM_LIST,
        on_hashes=True,
    ),
    MetadataSource.LAUNCHBOX: RescanRule(
        "launchbox_id",
        "launchbox_metadata",
        unmatched_supported=lambda p: p.slug in LAUNCHBOX_PLATFORM_LIST,
    ),
    MetadataSource.HASHEOUS: RescanRule(
        "hasheous_id",
        "hasheous_metadata",
        platform_supported=lambda p: p.hasheous_id,
        unmatched_supported=lambda p: p.slug in HASHEOUS_PLATFORM_LIST,
        on_hashes=True,
    ),
    MetadataSource.SGDB: RescanRule("sgdb_id", None),
    MetadataSource.FLASHPOINT: RescanRule(
        "flashpoint_id",
        "flashpoint_metadata",
        platform_supported=lambda p: p.slug in FLASHPOINT_PLATFORM_LIST,
    ),
    MetadataSource.HLTB: RescanRule(
        "hltb_id",
        "hltb_metadata",
        platform_supported=lambda p: p.slug in HLTB_PLATFORM_LIST,
    ),
    MetadataSource.DEMOZOO: RescanRule("demozoo_id", "demozoo_metadata"),
    MetadataSource.POUET: RescanRule("pouet_id", "pouet_metadata"),
    MetadataSource.CSDB: RescanRule("csdb_id", "csdb_metadata"),
    MetadataSource.STEAM: RescanRule(
        "steam_id",
        "steam_metadata",
        platform_supported=lambda p: p.slug in STEAM_PLATFORMS,
    ),
    MetadataSource.GAMELIST: RescanRule("gamelist_id", "gamelist_metadata"),
    MetadataSource.LIBRETRO: RescanRule(
        "libretro_id",
        None,
        platform_supported=lambda p: p.slug in LIBRETRO_PLATFORM_LIST,
    ),
}


def should_consult(
    source: MetadataSource,
    *,
    scan_type: ScanType,
    rom: Rom,
    platform: Platform,
    newly_added: bool,
    metadata_sources: Collection[str],
) -> bool:
    """Whether a scan asks `source` about `rom`."""
    rule = RESCAN_RULES[source]
    if source not in metadata_sources or not rule.platform_supported(platform):
        return False
    if newly_added or scan_type == ScanType.COMPLETE:
        return True
    if scan_type == ScanType.HASHES:
        return rule.on_hashes
    match_id = getattr(rom, rule.id_field)
    if scan_type == ScanType.UPDATE:
        return bool(match_id)
    if scan_type == ScanType.UNMATCHED:
        unmatched = not match_id or (
            rule.metadata_field is not None and not getattr(rom, rule.metadata_field)
        )
        return bool(unmatched and rule.unmatched_supported(platform))
    return False


def stored_match_id(source: MetadataSource, *, scan_type: ScanType, rom: Rom) -> Any:
    """The id a refresh refetches `source` by, or None when the scan matches anew."""
    # A stored id is often a manual match, so a refresh never trades it for a guess.
    rule = RESCAN_RULES[source]
    match_id = getattr(rom, rule.id_field)
    if not match_id:
        return None
    if scan_type == ScanType.UPDATE:
        return match_id
    if (
        scan_type == ScanType.UNMATCHED
        and rule.metadata_field is not None
        and not getattr(rom, rule.metadata_field)
    ):
        return match_id
    return None


def get_priority_ordered_metadata_sources(
    metadata_sources: list[MetadataSource], priority_type: str = "metadata"
) -> list[MetadataSource]:
    """Get metadata sources ordered by priority from config

    Args:
        metadata_sources: List of available metadata sources
        priority_type: Priority list to use: "metadata", "artwork", or an artwork
            field name (e.g. "url_cover") that can carry a per-field override.

    Returns:
        List of metadata sources ordered by priority
    """
    cnfg = cm.get_config()

    if priority_type == "metadata":
        priority_order = cnfg.SCAN_METADATA_PRIORITY
    else:
        # Per-field artwork overrides win, otherwise fall back to the shared
        # artwork priority list.
        priority_order = cnfg.SCAN_ARTWORK_PRIORITY_OVERRIDES.get(
            priority_type, cnfg.SCAN_ARTWORK_PRIORITY
        )

    # Filter priority order to only include sources that are available. A
    # source listed twice in config.yml keeps its first position.
    ordered_sources = list(
        dict.fromkeys(
            MetadataSource(source)
            for source in priority_order
            if source in metadata_sources
        )
    )

    # Add any remaining sources that weren't in the priority list
    remaining_sources = [
        MetadataSource(source)
        for source in metadata_sources
        if source not in ordered_sources
    ]

    return ordered_sources + remaining_sources


def get_enabled_metadata_sources() -> list[str]:
    """The metadata sources a library scan can use, per their provider's config."""
    handlers = {
        MetadataSource.IGDB: meta_igdb_handler,
        MetadataSource.SS: meta_ss_handler,
        MetadataSource.MOBY: meta_moby_handler,
        MetadataSource.RA: meta_ra_handler,
        MetadataSource.LAUNCHBOX: meta_launchbox_handler,
        MetadataSource.HASHEOUS: meta_hasheous_handler,
        MetadataSource.PLAYMATCH: meta_playmatch_handler,
        MetadataSource.SGDB: meta_sgdb_handler,
        MetadataSource.FLASHPOINT: meta_flashpoint_handler,
        MetadataSource.HLTB: meta_hltb_handler,
        MetadataSource.DEMOZOO: meta_demozoo_handler,
        MetadataSource.POUET: meta_pouet_handler,
        MetadataSource.CSDB: meta_csdb_handler,
        MetadataSource.STEAM: meta_steam_handler,
        MetadataSource.TGDB: meta_tgdb_handler,
        MetadataSource.LIBRETRO: meta_libretro_handler,
    }
    return [source for source, handler in handlers.items() if handler.is_enabled()]
