"""One rom's lookups against each metadata source during a scan."""

import dataclasses
import functools
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from adapters.services.screenscraper import ScreenScraperRateLimitError
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.filesystem.roms_handler import FSRom
from handler.metadata import (
    meta_csdb_handler,
    meta_demozoo_handler,
    meta_flashpoint_handler,
    meta_gamelist_handler,
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
)
from handler.metadata.csdb_handler import CsdbRom
from handler.metadata.demozoo_handler import DemozooRom
from handler.metadata.flashpoint_handler import FlashpointRom
from handler.metadata.gamelist_handler import GamelistRom
from handler.metadata.hasheous_handler import HasheousRom
from handler.metadata.hltb_handler import HLTBRom
from handler.metadata.igdb_handler import IGDBRom
from handler.metadata.launchbox_handler.media import populate_rom_specific_paths
from handler.metadata.launchbox_handler.types import LaunchboxRom
from handler.metadata.libretro_handler import LibretroRom
from handler.metadata.moby_handler import MobyGamesRom
from handler.metadata.playmatch_handler import (
    PLAYMATCH_SUPPORTED_SOURCES,
    PlaymatchRomMatch,
)
from handler.metadata.pouet_handler import PouetRom
from handler.metadata.ra_handler import RAGameRom
from handler.metadata.sgdb_handler import SGDBRom
from handler.metadata.ss_handler import (
    ScreenScraperExhaustedError,
    SSRom,
    note_rate_limited_rom,
)
from handler.metadata.steam_handler import SteamRom
from handler.scan.sources import (
    LOGGER_MODULE_NAME,
    MetadataSource,
    ScanType,
    should_consult,
    stored_match_id,
)
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.platform import Platform
from models.rom import Rom, RomFile
from utils import emoji


def get_main_platform_igdb_id(platform: Platform) -> int | None:
    cnfg = cm.get_config()

    main_platform_slug = cnfg.PLATFORMS_VERSIONS.get(platform.fs_slug.lower())
    if main_platform_slug:
        main_platform = db_platform_handler.get_platform_by_fs_slug(main_platform_slug)
        if main_platform:
            main_platform_igdb_id = main_platform.igdb_id
        else:
            igdb_platform = meta_igdb_handler.get_platform(main_platform_slug)
            main_platform_igdb_id = igdb_platform["igdb_id"]
            if not main_platform_igdb_id:
                main_platform_igdb_id = platform.igdb_id
    else:
        main_platform_igdb_id = platform.igdb_id
    return main_platform_igdb_id


async def resolve_launchbox_rom(
    *,
    rom: Rom,
    fs_name: str,
    platform_slug: str,
    scan_type: ScanType,
    playmatch_rom: PlaymatchRomMatch,
    remote_enabled: bool,
) -> LaunchboxRom:
    """Resolve a ROM's LaunchBox match, by ID where one is known, else by filename."""
    launchbox_id = stored_match_id(
        MetadataSource.LAUNCHBOX, scan_type=scan_type, rom=rom
    )
    if remote_enabled and launchbox_id:
        return await meta_launchbox_handler.get_rom_by_id(
            launchbox_id,
            remote_enabled=True,
            fs_name=fs_name,
            platform_slug=platform_slug,
        )

    launchbox_rom = LaunchboxRom(launchbox_id=None)

    if playmatch_rom["launchbox_id"] is not None and remote_enabled:
        log.debug(
            f"{hl(fs_name)} identified by Playmatch as LaunchBox "
            f"{hl(str(playmatch_rom['launchbox_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
            extra=LOGGER_MODULE_NAME,
        )
        launchbox_rom = await meta_launchbox_handler.get_rom_by_id(
            playmatch_rom["launchbox_id"],
            remote_enabled=True,
            fs_name=fs_name,
            platform_slug=platform_slug,
        )

    # Playmatch suggests an ID the metadata store may not hold, and on some
    # platforms it answers for nearly every ROM. Letting that miss stand would
    # strand the whole platform unmatched, so the filename lookup still runs.
    if not launchbox_rom.get("launchbox_id"):
        launchbox_rom = await meta_launchbox_handler.get_rom(
            fs_name,
            platform_slug,
            remote_enabled=remote_enabled,
        )

    return launchbox_rom


async def resolve_steam_rom(
    *,
    rom: Rom,
    fs_name: str,
    platform_slug: str,
    scan_type: ScanType,
) -> SteamRom:
    """Resolve a ROM's Steam match, by app ID where one is known, else by filename."""
    steam_id = stored_match_id(MetadataSource.STEAM, scan_type=scan_type, rom=rom)
    if steam_id:
        return await meta_steam_handler.get_rom_by_id(steam_id)

    return await meta_steam_handler.get_rom(fs_name, platform_slug)


@dataclass
class RomLookups:
    """One rom's lookups against each metadata source during a scan."""

    scan_type: ScanType
    platform: Platform
    rom: Rom
    fs_rom: FSRom
    rom_attrs: Mapping[str, Any]
    metadata_sources: list[str]
    newly_added: bool
    launchbox_remote_enabled: bool
    # Sources whose lookup actually ran. One skipped because the platform carries
    # no id for it never enters the set, so a rescan can't clear what it can't redo.
    attempted_sources: set[MetadataSource] = dataclasses.field(default_factory=set)
    # Sources this scan asked and never got an answer from. A miss they did not
    # rule out is not a coverage gap, so the outcome must not be reported as one.
    inconclusive_sources: set[MetadataSource] = dataclasses.field(default_factory=set)

    def note_inconclusive(self, source: MetadataSource) -> None:
        """Record a source that was consulted and never answered."""
        # It ruled nothing out, so it stops counting as attempted too and a
        # complete rescan keeps the id it already had.
        self.attempted_sources.discard(source)
        self.inconclusive_sources.add(source)

    def resolve_fetch(self, source: MetadataSource, result: Any, fallback: Any) -> Any:
        """Unwrap a gathered lookup, falling back to an empty match when it failed."""
        if not isinstance(result, BaseException):
            return result
        if not isinstance(result, Exception):
            raise result

        self.note_inconclusive(source)
        log.error(
            f"Error fetching {hl(source)} metadata for {hl(self.rom_attrs['fs_name'])}: {result}",
            extra=LOGGER_MODULE_NAME,
        )
        return fallback

    def consults(self, source: MetadataSource) -> bool:
        return should_consult(
            source,
            scan_type=self.scan_type,
            rom=self.rom,
            platform=self.platform,
            newly_added=self.newly_added,
            metadata_sources=self.metadata_sources,
        )

    # A fetcher that passes the platform's id on checks it first, so the id
    # narrows to an int.
    def attempts(self, source: MetadataSource) -> bool:
        """Whether to ask `source`, recording the attempt when it is asked."""
        if not self.consults(source):
            return False
        self.attempted_sources.add(source)
        return True

    @functools.cached_property
    def match_files(self) -> list[RomFile]:
        """Files used for hash-based metadata matching, fetched at most once."""
        return self.fs_rom["files"] or db_rom_handler.rom_files_for_rom_id(self.rom.id)

    def stored_id(self, source: MetadataSource) -> Any:
        return stored_match_id(source, scan_type=self.scan_type, rom=self.rom)

    async def fetch_playmatch_hash_match(self) -> PlaymatchRomMatch:
        # Playmatch's ids only feed other sources, so it runs when one of them will.
        if (
            meta_playmatch_handler.is_enabled()
            and MetadataSource.PLAYMATCH in self.metadata_sources
            and any(
                self.consults(MetadataSource(source))
                for source in PLAYMATCH_SUPPORTED_SOURCES
            )
        ):
            return await meta_playmatch_handler.lookup_rom(self.match_files)

        return PlaymatchRomMatch(
            igdb_id=None,
            moby_id=None,
            ss_id=None,
            launchbox_id=None,
            sgdb_id=None,
            ra_id=None,
            hasheous_id=None,
            tgdb_id=None,
            flashpoint_id=None,
            hltb_id=None,
            libretro_id=None,
            gamelist_id=None,
        )

    async def fetch_hasheous_hash_match(self) -> tuple[HasheousRom, bool]:
        if self.consults(MetadataSource.HASHEOUS):
            match, conclusive = await meta_hasheous_handler.lookup_rom(
                self.platform.slug, self.match_files
            )
            # Hasheous swallows its own failures, so an empty match that is not
            # conclusive is the only sign the lookup never got an answer. A
            # disabled handler reports the same flag without being consulted.
            if not conclusive and meta_hasheous_handler.is_enabled():
                self.note_inconclusive(MetadataSource.HASHEOUS)
            return match, conclusive

        return (
            HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None),
            False,
        )

    async def fetch_igdb_rom(
        self, playmatch_rom: PlaymatchRomMatch, hasheous_rom: HasheousRom
    ) -> IGDBRom:
        if self.platform.igdb_id and self.attempts(MetadataSource.IGDB):
            igdb_id = self.stored_id(MetadataSource.IGDB)
            if igdb_id:
                return await meta_igdb_handler.get_rom_by_id(self.rom, igdb_id)

            # Use Hasheous match to get the IGDB ID
            h_igdb_id = hasheous_rom.get("igdb_id")
            if h_igdb_id:
                log.debug(
                    f"{hl(self.rom_attrs['fs_name'])} identified by Hasheous as "
                    f"{hl(str(h_igdb_id), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_igdb_handler.get_rom_by_id(self.rom, h_igdb_id)

            # Use Playmatch matches to get the IGDB ID
            if playmatch_rom["igdb_id"] is not None:
                log.debug(
                    f"{hl(self.rom_attrs['fs_name'])} identified by Playmatch as "
                    f"{hl(str(playmatch_rom['igdb_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )

                return await meta_igdb_handler.get_rom_by_id(
                    self.rom, playmatch_rom["igdb_id"]
                )

            # If no matches found, use the file name to get the IGDB ID
            main_platform_igdb_id = get_main_platform_igdb_id(self.platform)
            return await meta_igdb_handler.get_rom(
                self.rom,
                self.rom_attrs["fs_name"],
                main_platform_igdb_id or self.platform.igdb_id,
            )

        return IGDBRom(igdb_id=None)

    async def fetch_gamelist_rom(self) -> GamelistRom:
        if self.attempts(MetadataSource.GAMELIST):
            return await meta_gamelist_handler.get_rom(
                self.rom_attrs["fs_name"], self.platform, self.rom
            )

        return GamelistRom(gamelist_id=None)

    async def fetch_flashpoint_rom(self) -> FlashpointRom:
        if self.attempts(MetadataSource.FLASHPOINT):
            flashpoint_id = self.stored_id(MetadataSource.FLASHPOINT)
            if flashpoint_id:
                return await meta_flashpoint_handler.get_rom_by_id(flashpoint_id)
            return await meta_flashpoint_handler.get_rom(
                self.rom_attrs["fs_name"], self.platform.slug
            )

        return FlashpointRom(flashpoint_id=None)

    async def fetch_libretro_rom(self) -> LibretroRom:
        if self.attempts(MetadataSource.LIBRETRO):
            return await meta_libretro_handler.get_rom(
                self.rom_attrs["fs_name"], self.platform.slug
            )

        return LibretroRom(libretro_id=None)

    async def fetch_hltb_rom(self) -> HLTBRom:
        if self.attempts(MetadataSource.HLTB):
            hltb_id = self.stored_id(MetadataSource.HLTB)
            if hltb_id:
                return await meta_hltb_handler.get_rom_by_id(hltb_id)

            return await meta_hltb_handler.get_rom(
                self.rom_attrs["fs_name"], self.platform.slug
            )

        return HLTBRom(hltb_id=None)

    async def fetch_demozoo_rom(self) -> DemozooRom:
        if self.attempts(MetadataSource.DEMOZOO):
            demozoo_id = self.stored_id(MetadataSource.DEMOZOO)
            if demozoo_id:
                return await meta_demozoo_handler.get_rom_by_id(demozoo_id)
            return await meta_demozoo_handler.get_rom(
                self.rom_attrs["fs_name"], self.platform.slug
            )
        return DemozooRom(demozoo_id=None)

    async def fetch_pouet_rom(self) -> PouetRom:
        if self.attempts(MetadataSource.POUET):
            if self.rom.pouet_id:
                return await meta_pouet_handler.get_rom_by_id(int(self.rom.pouet_id))
            return await meta_pouet_handler.get_rom(
                self.rom_attrs["fs_name"], self.platform.slug
            )
        return PouetRom(pouet_id=None)

    async def fetch_csdb_rom(self) -> CsdbRom:
        if self.attempts(MetadataSource.CSDB):
            if self.rom.csdb_id:
                return await meta_csdb_handler.get_rom_by_id(int(self.rom.csdb_id))
            return await meta_csdb_handler.get_rom(
                self.rom_attrs["fs_name"], self.platform.slug
            )
        return CsdbRom(csdb_id=None)

    async def fetch_steam_rom(self) -> SteamRom:
        if self.attempts(MetadataSource.STEAM):
            return await resolve_steam_rom(
                rom=self.rom,
                fs_name=str(self.rom_attrs["fs_name"]),
                platform_slug=self.platform.slug,
                scan_type=self.scan_type,
            )

        return SteamRom(steam_id=None)

    async def fetch_moby_rom(self, playmatch_rom: PlaymatchRomMatch) -> MobyGamesRom:
        if self.platform.moby_id and self.attempts(MetadataSource.MOBY):
            moby_id = self.stored_id(MetadataSource.MOBY)
            if moby_id:
                return await meta_moby_handler.get_rom_by_id(moby_id)

            if playmatch_rom["moby_id"] is not None:
                log.debug(
                    f"{hl(self.rom_attrs['fs_name'])} identified by Playmatch as MobyGames "
                    f"{hl(str(playmatch_rom['moby_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_moby_handler.get_rom_by_id(playmatch_rom["moby_id"])

            return await meta_moby_handler.get_rom(
                self.rom,
                self.rom_attrs["fs_name"],
                platform_moby_id=self.platform.moby_id,
            )

        return MobyGamesRom(moby_id=None)

    async def fetch_ss_rom(self, playmatch_rom: PlaymatchRomMatch) -> SSRom:
        if self.platform.ss_id and self.attempts(MetadataSource.SS):
            # A breaker answering in ScreenScraper's place rules nothing out for
            # this rom, whichever of the lookups below it short-circuits.
            short_circuited = False
            try:
                ss_id = self.stored_id(MetadataSource.SS)
                if ss_id:
                    # With the files, the refetch still finds our own dump among
                    # the game's, so a rescan keeps the tags the hash earned.
                    return await meta_ss_handler.get_rom_by_id(
                        self.rom, ss_id, self.match_files
                    )

                # Use Playmatch's hash-based id when available
                if playmatch_rom["ss_id"] is not None:
                    log.debug(
                        f"{hl(self.rom_attrs['fs_name'])} identified by Playmatch as ScreenScraper "
                        f"{hl(str(playmatch_rom['ss_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                        extra=LOGGER_MODULE_NAME,
                    )
                    return await meta_ss_handler.get_rom_by_id(
                        self.rom, playmatch_rom["ss_id"], self.match_files
                    )

                # Use the file hashes for lookup
                try:
                    game_by_hash, is_not_game = await meta_ss_handler.lookup_rom(
                        self.rom, self.platform.ss_id, self.match_files
                    )
                except ScreenScraperExhaustedError:
                    # The filename lookup below still derives a name for some
                    # platforms, and the breaker can clear before it runs.
                    short_circuited = True
                else:
                    if game_by_hash.get("ss_id") or is_not_game:
                        return game_by_hash

                # Fallback to the filename
                return await meta_ss_handler.get_rom(
                    self.rom,
                    self.rom_attrs["fs_name"],
                    platform_ss_id=self.platform.ss_id,
                )
            except ScreenScraperExhaustedError as exc:
                short_circuited = True
                return exc.fallback
            except ScreenScraperRateLimitError:
                # The per-minute budget is already spent, so give up on this ROM
                # rather than spending a retried request on the fallback lookups.
                note_rate_limited_rom(self.rom_attrs["fs_name"])
                short_circuited = True
                return SSRom(ss_id=None)
            finally:
                if short_circuited:
                    self.note_inconclusive(MetadataSource.SS)

        return SSRom(ss_id=None)

    async def fetch_launchbox_rom(
        self, playmatch_rom: PlaymatchRomMatch
    ) -> LaunchboxRom:
        if self.attempts(MetadataSource.LAUNCHBOX):
            launchbox_rom = await resolve_launchbox_rom(
                rom=self.rom,
                fs_name=str(self.rom_attrs["fs_name"]),
                platform_slug=self.platform.slug,
                scan_type=self.scan_type,
                playmatch_rom=playmatch_rom,
                remote_enabled=self.launchbox_remote_enabled,
            )

            metadata = launchbox_rom.get("launchbox_metadata")
            if metadata:
                populate_rom_specific_paths(metadata, self.rom)

            return launchbox_rom

        return LaunchboxRom(launchbox_id=None)

    async def fetch_ra_rom(self) -> RAGameRom:
        if self.attempts(MetadataSource.RA):
            ra_id = self.stored_id(MetadataSource.RA)
            if ra_id:
                return await meta_ra_handler.get_rom_by_id(
                    rom=self.rom, ra_id=ra_id, ra_hash=self.rom_attrs["ra_hash"]
                )
            return await meta_ra_handler.get_rom(
                rom=self.rom, ra_hash=self.rom_attrs["ra_hash"]
            )

        return RAGameRom(ra_id=None)

    async def fetch_hasheous_rom(self, hasheous_rom: HasheousRom) -> HasheousRom:
        if self.consults(MetadataSource.HASHEOUS):
            # The hash lookup is the only thing that identifies a rom here, so one
            # that never answered leaves a complete rescan nothing to redo.
            if MetadataSource.HASHEOUS not in self.inconclusive_sources:
                self.attempted_sources.add(MetadataSource.HASHEOUS)
            return await meta_hasheous_handler.get_igdb_game(hasheous_rom)

        return HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None)

    async def fetch_sgdb_rom(
        self,
        playmatch_rom: PlaymatchRomMatch,
        provider_names: list[str | None],
        *,
        scene_locked: bool,
    ) -> SGDBRom:
        # SGDB searches by title (and by IGDB's similar-name match). That is
        # the same collision a scene production is locked out of.
        if scene_locked or not self.attempts(MetadataSource.SGDB):
            return SGDBRom(sgdb_id=None)

        if self.scan_type == ScanType.UPDATE and self.rom.sgdb_id:
            return await meta_sgdb_handler.get_rom_by_id(self.rom.sgdb_id)

        if playmatch_rom["sgdb_id"] is not None:
            log.debug(
                f"{hl(self.rom_attrs['fs_name'])} identified by Playmatch as SteamGridDB "
                f"{hl(str(playmatch_rom['sgdb_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                extra=LOGGER_MODULE_NAME,
            )
            return await meta_sgdb_handler.get_rom_by_id(playmatch_rom["sgdb_id"])

        file_name_no_tags = fs_rom_handler.get_file_name_with_no_tags(
            str(self.rom_attrs["fs_name"])
        )
        valid_names = [name for name in [*provider_names, file_name_no_tags] if name]
        return await meta_sgdb_handler.get_details_by_names(valid_names)


# The sources whose matched names SteamGridDB searches by, in order.
SGDB_NAME_SOURCES: Final = (
    MetadataSource.IGDB,
    MetadataSource.HASHEOUS,
    MetadataSource.SS,
    MetadataSource.MOBY,
    MetadataSource.LAUNCHBOX,
    MetadataSource.GAMELIST,
)
