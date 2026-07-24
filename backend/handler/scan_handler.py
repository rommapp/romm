import asyncio
import enum
import functools
from typing import Any

import socketio  # type: ignore

from config.config_manager import config_manager as cm
from endpoints.responses.rom import SimpleRomSchema
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_asset_handler, fs_firmware_handler, fs_rom_handler
from handler.filesystem.roms_handler import FSRom
from handler.metadata import (
    meta_flashpoint_handler,
    meta_gamelist_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_libretro_handler,
    meta_moby_handler,
    meta_playmatch_handler,
    meta_ra_handler,
    meta_sgdb_handler,
    meta_ss_handler,
    meta_tgdb_handler,
)
from handler.metadata.flashpoint_handler import FLASHPOINT_PLATFORM_LIST, FlashpointRom
from handler.metadata.gamelist_handler import GamelistRom
from handler.metadata.hasheous_handler import HASHEOUS_PLATFORM_LIST, HasheousRom
from handler.metadata.hltb_handler import HLTB_PLATFORM_LIST, HLTBRom
from handler.metadata.igdb_handler import IGDB_PLATFORM_LIST, IGDBRom
from handler.metadata.launchbox_handler.media import populate_rom_specific_paths
from handler.metadata.launchbox_handler.platforms import LAUNCHBOX_PLATFORM_LIST
from handler.metadata.launchbox_handler.types import LaunchboxRom
from handler.metadata.libretro_handler import LIBRETRO_PLATFORM_LIST, LibretroRom
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST, MobyGamesRom
from handler.metadata.playmatch_handler import (
    PLAYMATCH_SUPPORTED_SOURCES,
    PlaymatchRomMatch,
)
from handler.metadata.ra_handler import RA_PLATFORM_LIST, RAGameRom
from handler.metadata.sgdb_handler import SGDBRom
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST, SSRom
from logger.formatter import BLUE, LIGHTYELLOW
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import MemoryCardVersion, Save, Screenshot, State
from models.firmware import Firmware
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User
from utils import emoji
from utils.audio_tags import persist_embedded_cover, remove_persisted_cover

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
    GAMELIST = "gamelist"  # ES-DE gamelist.xml
    LIBRETRO = "libretro"  # Libretro thumbnails
    PLAYMATCH = "playmatch"  # Playmatch


def get_main_platform_igdb_id(platform: Platform):
    cnfg = cm.get_config()

    if platform.fs_slug in cnfg.PLATFORMS_VERSIONS.keys():
        main_platform_slug = cnfg.PLATFORMS_VERSIONS[platform.fs_slug]
        main_platform = db_platform_handler.get_platform_by_fs_slug(main_platform_slug)
        if main_platform:
            main_platform_igdb_id = main_platform.igdb_id
        else:
            main_platform = meta_igdb_handler.get_platform(main_platform_slug)
            main_platform_igdb_id = main_platform["igdb_id"]
            if not main_platform_igdb_id:
                main_platform_igdb_id = platform.igdb_id
    else:
        main_platform_igdb_id = platform.igdb_id
    return main_platform_igdb_id


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

    # Filter priority order to only include sources that are available
    ordered_sources = [
        MetadataSource(source)
        for source in priority_order
        if source in metadata_sources
    ]

    # Add any remaining sources that weren't in the priority list
    remaining_sources = [
        MetadataSource(source)
        for source in metadata_sources
        if source not in ordered_sources
    ]

    return ordered_sources + remaining_sources


def persist_soundtrack_cover(rom_file: RomFile, rom: Rom) -> None:
    """Persist a scanned soundtrack file's embedded cover and record its path on
    the track_meta row. No-op for non-soundtrack files or ones without a cover."""
    track_meta = rom_file.track_meta
    if not (rom_file.category == RomFileCategory.SOUNDTRACK and track_meta):
        return

    if not track_meta.has_embedded_cover:
        # The cover was stripped from the file since the last scan. Keep the
        # path when the unlink fails, so the next scan retries it rather than
        # stranding the file with nothing pointing at it.
        if track_meta.cover_path and remove_persisted_cover(track_meta.cover_path):
            db_rom_handler.upsert_track_meta(rom_file.id, rom.id, {"cover_path": None})
        return

    abs_audio_path = fs_rom_handler.validate_path(rom_file.full_path)
    cover_path = persist_embedded_cover(
        audio_full_path=str(abs_audio_path),
        platform_id=rom.platform_id,
        rom_id=rom.id,
        file_id=rom_file.id,
    )
    if cover_path:
        db_rom_handler.upsert_track_meta(
            rom_file.id, rom.id, {"cover_path": cover_path}
        )
    else:
        log.error(f"[audio_tags] cover persist failed for {abs_audio_path}")
        db_rom_handler.upsert_track_meta(
            rom_file.id, rom.id, {"has_embedded_cover": False}
        )


async def scan_platform(
    fs_slug: str,
    fs_platforms: list[str],
) -> Platform:
    """Get platform details

    Args:
        fs_slug: short name of the platform
    Returns
        Platform object
    """
    platform_attrs: dict[str, Any] = {}
    platform_attrs["fs_slug"] = fs_slug

    cnfg = cm.get_config()
    swapped_platform_bindings = {v: k for k, v in cnfg.PLATFORMS_BINDING.items()}
    swapped_platform_versions = {v: k for k, v in cnfg.PLATFORMS_VERSIONS.items()}

    # Sometimes users change the name of the folder, so we try to match it with the config
    if fs_slug not in fs_platforms:
        log.warning(
            f"{hl(fs_slug)} not found in file system, trying to match via config",
            extra=LOGGER_MODULE_NAME,
        )
        if fs_slug in swapped_platform_bindings.keys():
            platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
            if platform:
                platform_attrs["fs_slug"] = swapped_platform_bindings[platform.slug]
        elif fs_slug in swapped_platform_versions.keys():
            platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
            if platform:
                platform_attrs["fs_slug"] = swapped_platform_versions[platform.slug]

    try:
        if fs_slug in cnfg.PLATFORMS_BINDING.keys():
            platform_attrs["slug"] = cnfg.PLATFORMS_BINDING[fs_slug]
        elif fs_slug in cnfg.PLATFORMS_VERSIONS.keys():
            platform_attrs["slug"] = cnfg.PLATFORMS_VERSIONS[fs_slug]
        else:
            platform_attrs["slug"] = fs_slug
    except (KeyError, TypeError, AttributeError):
        platform_attrs["slug"] = fs_slug

    igdb_platform = meta_igdb_handler.get_platform(platform_attrs["slug"])
    moby_platform = meta_moby_handler.get_platform(platform_attrs["slug"])
    ss_platform = meta_ss_handler.get_platform(platform_attrs["slug"])
    ra_platform = meta_ra_handler.get_platform(platform_attrs["slug"])
    launchbox_platform = meta_launchbox_handler.get_platform(platform_attrs["slug"])
    hasheous_platform = meta_hasheous_handler.get_platform(platform_attrs["slug"])
    tgdb_platform = meta_tgdb_handler.get_platform(platform_attrs["slug"])
    flashpoint_platform = meta_flashpoint_handler.get_platform(platform_attrs["slug"])
    hltb_platform = meta_hltb_handler.get_platform(platform_attrs["slug"])
    libretro_platform = meta_libretro_handler.get_platform(platform_attrs["slug"])

    platform_attrs["name"] = platform_attrs["slug"].replace("-", " ").title()
    platform_attrs.update(
        {
            **libretro_platform,
            **hltb_platform,
            **flashpoint_platform,
            **tgdb_platform,
            **hasheous_platform,
            **launchbox_platform,
            **ra_platform,
            **moby_platform,
            **ss_platform,
            **igdb_platform,
            "igdb_id": igdb_platform.get("igdb_id")
            or hasheous_platform.get("igdb_id")
            or None,
            "ra_id": ra_platform.get("ra_id") or hasheous_platform.get("ra_id") or None,
            "tgdb_id": moby_platform.get("tgdb_id")
            or hasheous_platform.get("tgdb_id")
            or tgdb_platform.get("tgdb_id")
            or None,
            "name": igdb_platform.get("name")
            or ss_platform.get("name")
            or moby_platform.get("name")
            or ra_platform.get("name")
            or launchbox_platform.get("name")
            or hasheous_platform.get("name")
            or tgdb_platform.get("name")
            or flashpoint_platform.get("name")
            or hltb_platform.get("name")
            or platform_attrs["slug"].replace("-", " ").title(),
            "url_logo": igdb_platform.get("url_logo")
            or tgdb_platform.get("url_logo")
            or "",
        }
    )

    if (
        platform_attrs["igdb_id"]
        or platform_attrs["moby_id"]
        or platform_attrs["ss_id"]
        or platform_attrs["ra_id"]
        or platform_attrs["launchbox_id"]
        or hasheous_platform["hasheous_id"]
        or tgdb_platform["tgdb_id"]
        or flashpoint_platform["flashpoint_id"]
        or hltb_platform["hltb_slug"]
        or libretro_platform["libretro_slug"]
    ):
        log.info(
            f"Folder {hl(platform_attrs['slug'])}[{hl(fs_slug, color=LIGHTYELLOW)}] identified as {hl(platform_attrs['name'], color=BLUE)} {emoji.EMOJI_VIDEO_GAME}",
            extra={"module_name": "scan"},
        )
    else:
        log.warning(
            f"Platform {hl(platform_attrs['slug'])} not identified {emoji.EMOJI_CROSS_MARK}",
            extra=LOGGER_MODULE_NAME,
        )

    platform_attrs["missing_from_fs"] = False
    return Platform(**platform_attrs)


async def scan_firmware(
    platform: Platform,
    file_name: str,
    firmware: Firmware | None = None,
) -> Firmware:
    firmware_path = fs_firmware_handler.get_firmware_fs_structure(platform.fs_slug)

    # Set default properties
    firmware_attrs = {
        "id": firmware.id if firmware else None,
        "platform_id": platform.id,
    }

    file_path = f"{firmware_path}/{file_name}"
    file_size = await fs_firmware_handler.get_file_size(file_path)

    firmware_attrs.update(
        {
            "file_path": firmware_path,
            "file_name": file_name,
            "file_size_bytes": file_size,
        }
    )

    file_hashes = await fs_firmware_handler.calculate_file_hashes(
        firmware_path=firmware_path,
        file_name=file_name,
    )

    firmware_attrs.update(**file_hashes)

    return Firmware(**firmware_attrs)


async def scan_rom(
    scan_type: ScanType,
    platform: Platform,
    rom: Rom,
    fs_rom: FSRom,
    metadata_sources: list[str],
    newly_added: bool,
    launchbox_remote_enabled: bool = True,
    playmatch_enabled: bool = True,
    socket_manager: socketio.AsyncRedisManager | None = None,
) -> Rom:
    rom_attrs = {
        "id": rom.id,
        "platform_id": platform.id,
        "fs_name": fs_rom["fs_name"],
        "fs_path": rom.fs_path,
        "regions": rom.regions,
        "revision": rom.revision,
        "languages": rom.languages,
        "tags": rom.tags,
        "crc_hash": rom.crc_hash,
        "md5_hash": rom.md5_hash,
        "sha1_hash": rom.sha1_hash,
        "ra_hash": rom.ra_hash,
        "fs_size_bytes": rom.fs_size_bytes,
    }

    # Check if files have been parsed and hashed
    if len(fs_rom["files"]) > 0:
        filesize = sum([file.file_size_bytes for file in fs_rom["files"]])
        rom_attrs.update(
            {
                "crc_hash": fs_rom["crc_hash"],
                "md5_hash": fs_rom["md5_hash"],
                "sha1_hash": fs_rom["sha1_hash"],
                "ra_hash": fs_rom["ra_hash"],
                "fs_size_bytes": filesize,
            }
        )

    # Update properties from existing rom if not a complete rescan
    if not newly_added and scan_type != ScanType.COMPLETE:
        rom_attrs.update(
            {
                "name": rom.name,
                "name_sort_key": rom.name_sort_key,
                "slug": rom.slug,
                "summary": rom.summary,
                "url_cover": rom.url_cover,
                "url_screenshots": rom.url_screenshots,
                "url_manual": rom.url_manual,
                "path_cover_s": rom.path_cover_s,
                "path_cover_l": rom.path_cover_l,
                "path_screenshots": rom.path_screenshots,
                "path_manual": rom.path_manual,
                "igdb_id": rom.igdb_id,
                "moby_id": rom.moby_id,
                "ss_id": rom.ss_id,
                "sgdb_id": rom.sgdb_id,
                "ra_id": rom.ra_id,
                "launchbox_id": rom.launchbox_id,
                "hasheous_id": rom.hasheous_id,
                "tgdb_id": rom.tgdb_id,
                "gamelist_id": rom.gamelist_id,
                "flashpoint_id": rom.flashpoint_id,
                "hltb_id": rom.hltb_id,
                "libretro_id": rom.libretro_id,
                "igdb_metadata": rom.igdb_metadata,
                "moby_metadata": rom.moby_metadata,
                "ss_metadata": rom.ss_metadata,
                "ra_metadata": rom.ra_metadata,
                "launchbox_metadata": rom.launchbox_metadata,
                "hasheous_metadata": rom.hasheous_metadata,
                "gamelist_metadata": rom.gamelist_metadata,
                "flashpoint_metadata": rom.flashpoint_metadata,
                "hltb_metadata": rom.hltb_metadata,
            }
        )

    @functools.cache
    def get_match_files() -> list[RomFile]:
        """Files used for hash-based metadata matching, fetched at most once."""
        return fs_rom["files"] or db_rom_handler.rom_files_for_rom_id(rom.id)

    async def fetch_playmatch_hash_match() -> PlaymatchRomMatch:
        if (
            meta_playmatch_handler.is_enabled()
            and MetadataSource.PLAYMATCH in metadata_sources
            and any(PLAYMATCH_SUPPORTED_SOURCES.intersection(metadata_sources))
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or scan_type == ScanType.UPDATE
                or scan_type == ScanType.UNMATCHED
            )
        ):
            return await meta_playmatch_handler.lookup_rom(get_match_files())

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

    async def fetch_hasheous_hash_match() -> HasheousRom:
        if (
            MetadataSource.HASHEOUS in metadata_sources
            and platform.hasheous_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.hasheous_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and (not rom.hasheous_id or not rom.hasheous_metadata)
                    and rom.platform_slug in HASHEOUS_PLATFORM_LIST
                )
            )
        ):
            return await meta_hasheous_handler.lookup_rom(
                platform.slug, get_match_files()
            )

        return HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None)

    _added_rom = db_rom_handler.add_rom(Rom(**rom_attrs))
    _added_rom.is_identifying = True

    if socket_manager:
        await socket_manager.emit(
            "scan:scanning_rom",
            {
                **SimpleRomSchema.from_orm_with_factory(_added_rom).model_dump(
                    exclude={
                        "created_at",
                        "updated_at",
                        "rom_user",
                        "last_modified",
                        "files",
                        "sibling_roms",
                    }
                ),
            },
        )

    # Run hash fetches concurrently
    (
        playmatch_hash_match,
        hasheous_hash_match,
    ) = await asyncio.gather(
        fetch_playmatch_hash_match(),
        fetch_hasheous_hash_match(),
    )

    async def fetch_igdb_rom(
        playmatch_rom: PlaymatchRomMatch, hasheous_rom: HasheousRom
    ) -> IGDBRom:
        if (
            MetadataSource.IGDB in metadata_sources
            and platform.igdb_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.igdb_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and (not rom.igdb_id or not rom.igdb_metadata)
                    and rom.platform_slug in IGDB_PLATFORM_LIST
                )
            )
        ):
            # Use Hasheous match to get the IGDB ID
            h_igdb_id = hasheous_rom.get("igdb_id")
            if h_igdb_id:
                log.debug(
                    f"{hl(rom_attrs['fs_name'])} identified by Hasheous as "
                    f"{hl(str(h_igdb_id), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_igdb_handler.get_rom_by_id(rom, h_igdb_id)

            # Use Playmatch matches to get the IGDB ID
            if playmatch_rom["igdb_id"] is not None:
                log.debug(
                    f"{hl(rom_attrs['fs_name'])} identified by Playmatch as "
                    f"{hl(str(playmatch_rom['igdb_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )

                return await meta_igdb_handler.get_rom_by_id(
                    rom, playmatch_rom["igdb_id"]
                )

            main_platform_igdb_id = get_main_platform_igdb_id(platform)
            if scan_type == ScanType.UPDATE and rom.igdb_id:
                # Use the ID to refetch the metadata from IGDB
                return await meta_igdb_handler.get_rom_by_id(rom, rom.igdb_id)
            else:
                # If no matches found, use the file name to get the IGDB ID
                return await meta_igdb_handler.get_rom(
                    rom,
                    rom_attrs["fs_name"],
                    main_platform_igdb_id or platform.igdb_id,
                )

        return IGDBRom(igdb_id=None)

    async def fetch_gamelist_rom() -> GamelistRom:
        if MetadataSource.GAMELIST in metadata_sources and (
            newly_added
            or scan_type == ScanType.COMPLETE
            or (scan_type == ScanType.UPDATE and rom.gamelist_id)
            or (
                scan_type == ScanType.UNMATCHED
                and (not rom.gamelist_id or not rom.gamelist_metadata)
            )
        ):
            return await meta_gamelist_handler.get_rom(
                rom_attrs["fs_name"], platform, rom
            )

        return GamelistRom(gamelist_id=None)

    async def fetch_flashpoint_rom() -> FlashpointRom:
        if (
            MetadataSource.FLASHPOINT in metadata_sources
            and platform.slug in FLASHPOINT_PLATFORM_LIST
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.flashpoint_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and (not rom.flashpoint_id or not rom.flashpoint_metadata)
                    and platform.slug in FLASHPOINT_PLATFORM_LIST
                )
            )
        ):
            if (scan_type == ScanType.UPDATE and rom.flashpoint_id) or (
                scan_type == ScanType.UNMATCHED
                and rom.flashpoint_id
                and not rom.flashpoint_metadata
            ):
                return await meta_flashpoint_handler.get_rom_by_id(rom.flashpoint_id)
            else:
                return await meta_flashpoint_handler.get_rom(
                    rom_attrs["fs_name"], platform.slug
                )

        return FlashpointRom(flashpoint_id=None)

    async def fetch_libretro_rom() -> LibretroRom:
        if (
            MetadataSource.LIBRETRO in metadata_sources
            and platform.slug in LIBRETRO_PLATFORM_LIST
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.libretro_id)
                or (scan_type == ScanType.UNMATCHED and not rom.libretro_id)
            )
        ):
            return await meta_libretro_handler.get_rom(
                rom_attrs["fs_name"], platform.slug
            )

        return LibretroRom(libretro_id=None)

    async def fetch_hltb_rom() -> HLTBRom:
        if (
            MetadataSource.HLTB in metadata_sources
            and platform.slug in HLTB_PLATFORM_LIST
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.hltb_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and (not rom.hltb_id or not rom.hltb_metadata)
                )
            )
        ):
            return await meta_hltb_handler.get_rom(rom_attrs["fs_name"], platform.slug)

        return HLTBRom(hltb_id=None)

    async def fetch_moby_rom(playmatch_rom: PlaymatchRomMatch) -> MobyGamesRom:
        if (
            MetadataSource.MOBY in metadata_sources
            and platform.moby_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.moby_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and (not rom.moby_id or not rom.moby_metadata)
                    and rom.platform_slug in MOBYGAMES_PLATFORM_LIST
                )
            )
        ):
            if scan_type == ScanType.UPDATE and rom.moby_id:
                return await meta_moby_handler.get_rom_by_id(rom.moby_id)

            if playmatch_rom["moby_id"] is not None:
                log.debug(
                    f"{hl(rom_attrs['fs_name'])} identified by Playmatch as MobyGames "
                    f"{hl(str(playmatch_rom['moby_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_moby_handler.get_rom_by_id(playmatch_rom["moby_id"])

            return await meta_moby_handler.get_rom(
                rom_attrs["fs_name"], platform_moby_id=platform.moby_id
            )

        return MobyGamesRom(moby_id=None)

    async def fetch_ss_rom(playmatch_rom: PlaymatchRomMatch) -> SSRom:
        if (
            MetadataSource.SS in metadata_sources
            and platform.ss_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.ss_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and (not rom.ss_id or not rom.ss_metadata)
                    and rom.platform_slug in SCREENSAVER_PLATFORM_LIST
                )
            )
        ):
            # Use the ID to refetch metadata
            if scan_type == ScanType.UPDATE and rom.ss_id:
                return await meta_ss_handler.get_rom_by_id(rom, rom.ss_id)

            # Use Playmatch's hash-based id when available
            if playmatch_rom["ss_id"] is not None:
                log.debug(
                    f"{hl(rom_attrs['fs_name'])} identified by Playmatch as ScreenScraper "
                    f"{hl(str(playmatch_rom['ss_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_ss_handler.get_rom_by_id(rom, playmatch_rom["ss_id"])

            # Use the file hashes for lookup
            game_by_hash, is_not_game = await meta_ss_handler.lookup_rom(
                rom, platform.ss_id, get_match_files()
            )
            if game_by_hash.get("ss_id") or is_not_game:
                return game_by_hash

            # Fallback to the filename
            return await meta_ss_handler.get_rom(
                rom, rom_attrs["fs_name"], platform_ss_id=platform.ss_id
            )

        return SSRom(ss_id=None)

    async def fetch_launchbox_rom(
        platform_slug: str, playmatch_rom: PlaymatchRomMatch
    ) -> LaunchboxRom:
        if MetadataSource.LAUNCHBOX in metadata_sources and (
            newly_added
            or scan_type == ScanType.COMPLETE
            or (scan_type == ScanType.UPDATE and rom.launchbox_id)
            or (
                scan_type == ScanType.UNMATCHED
                and (not rom.launchbox_id or not rom.launchbox_metadata)
                and rom.platform_slug in LAUNCHBOX_PLATFORM_LIST
            )
        ):
            if (
                scan_type == ScanType.UPDATE
                and rom.launchbox_id
                and launchbox_remote_enabled
            ):
                launchbox_rom = await meta_launchbox_handler.get_rom_by_id(
                    rom.launchbox_id,
                    remote_enabled=True,
                    fs_name=rom_attrs["fs_name"],
                    platform_slug=platform_slug,
                )
            elif (
                scan_type == ScanType.UNMATCHED
                and rom.launchbox_id
                and not rom.launchbox_metadata
                and launchbox_remote_enabled
            ):
                # ID was set manually but metadata was never fetched
                launchbox_rom = await meta_launchbox_handler.get_rom_by_id(
                    rom.launchbox_id,
                    remote_enabled=True,
                    fs_name=rom_attrs["fs_name"],
                    platform_slug=platform_slug,
                )
            elif playmatch_rom["launchbox_id"] is not None and launchbox_remote_enabled:
                log.debug(
                    f"{hl(rom_attrs['fs_name'])} identified by Playmatch as LaunchBox "
                    f"{hl(str(playmatch_rom['launchbox_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )
                launchbox_rom = await meta_launchbox_handler.get_rom_by_id(
                    playmatch_rom["launchbox_id"],
                    remote_enabled=True,
                    fs_name=rom_attrs["fs_name"],
                    platform_slug=platform_slug,
                )
            else:
                launchbox_rom = await meta_launchbox_handler.get_rom(
                    rom_attrs["fs_name"],
                    platform_slug,
                    remote_enabled=launchbox_remote_enabled,
                )

            metadata = launchbox_rom.get("launchbox_metadata")
            if metadata:
                populate_rom_specific_paths(metadata, rom)

            return launchbox_rom

        return LaunchboxRom(launchbox_id=None)

    async def fetch_ra_rom(hasheous_rom: HasheousRom) -> RAGameRom:
        if (
            MetadataSource.RA in metadata_sources
            and platform.ra_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or scan_type == ScanType.HASHES
                or (scan_type == ScanType.UPDATE and rom.ra_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and (not rom.ra_id or not rom.ra_metadata)
                    and rom.platform_slug in RA_PLATFORM_LIST
                )
            )
        ):
            # Use Hasheous match to get the RA ID
            h_ra_id = hasheous_rom.get("ra_id")
            if h_ra_id:
                log.debug(
                    f"{hl(rom_attrs['fs_name'])} identified by Hasheous as "
                    f"{hl(str(h_ra_id), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_ra_handler.get_rom_by_id(rom=rom, ra_id=h_ra_id)

            if (scan_type == ScanType.UPDATE and rom.ra_id) or (
                scan_type == ScanType.UNMATCHED and rom.ra_id and not rom.ra_metadata
            ):
                return await meta_ra_handler.get_rom_by_id(rom=rom, ra_id=rom.ra_id)
            else:
                return await meta_ra_handler.get_rom(
                    rom=rom, ra_hash=rom_attrs["ra_hash"]
                )

        return RAGameRom(ra_id=None)

    async def fetch_hasheous_rom(hasheous_rom: HasheousRom) -> HasheousRom:
        if (
            MetadataSource.HASHEOUS in metadata_sources
            and platform.hasheous_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.hasheous_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and (not rom.hasheous_id or not rom.hasheous_metadata)
                    and rom.platform_slug in HASHEOUS_PLATFORM_LIST
                )
            )
        ):
            (
                igdb_game,
                ra_game,
            ) = await asyncio.gather(
                meta_hasheous_handler.get_igdb_game(hasheous_rom),
                meta_hasheous_handler.get_ra_game(hasheous_rom),
            )

            return HasheousRom(
                {
                    **hasheous_rom,
                    **ra_game,
                    **igdb_game,
                }
            )

        return HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None)

    # Run metadata fetches concurrently. One provider raising must not discard the
    # others' results for this ROM, so each failure falls back to an empty match.
    provider_fetches = (
        (
            fetch_igdb_rom(playmatch_hash_match, hasheous_hash_match),
            IGDBRom(igdb_id=None),
        ),
        (fetch_moby_rom(playmatch_hash_match), MobyGamesRom(moby_id=None)),
        (fetch_ss_rom(playmatch_hash_match), SSRom(ss_id=None)),
        (fetch_ra_rom(hasheous_hash_match), RAGameRom(ra_id=None)),
        (
            fetch_launchbox_rom(platform.slug, playmatch_hash_match),
            LaunchboxRom(launchbox_id=None),
        ),
        (
            fetch_hasheous_rom(hasheous_hash_match),
            HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None),
        ),
        (fetch_flashpoint_rom(), FlashpointRom(flashpoint_id=None)),
        (fetch_hltb_rom(), HLTBRom(hltb_id=None)),
        (fetch_gamelist_rom(), GamelistRom(gamelist_id=None)),
        (fetch_libretro_rom(), LibretroRom(libretro_id=None)),
    )
    fetch_results = await asyncio.gather(
        *(coro for coro, _ in provider_fetches), return_exceptions=True
    )

    resolved: list[Any] = []
    for (_, fallback), result in zip(provider_fetches, fetch_results, strict=True):
        if isinstance(result, BaseException):
            if not isinstance(result, Exception):
                raise result
            provider = fallback.__class__.__name__
            log.error(
                f"Error fetching {hl(provider)} metadata for {hl(rom_attrs['fs_name'])}: {result}",
                extra=LOGGER_MODULE_NAME,
            )
            resolved.append(fallback)
        else:
            resolved.append(result)

    (
        igdb_handler_rom,
        moby_handler_rom,
        ss_handler_rom,
        ra_handler_rom,
        launchbox_handler_rom,
        hasheous_handler_rom,
        flashpoint_handler_rom,
        hltb_handler_rom,
        gamelist_handler_rom,
        libretro_handler_rom,
    ) = resolved

    metadata_handlers: dict[MetadataSource, dict] = {
        MetadataSource.IGDB: {
            "handler": igdb_handler_rom,
            "id_field": "igdb_id",
            "metadata_field": "igdb_metadata",
        },
        MetadataSource.MOBY: {
            "handler": moby_handler_rom,
            "id_field": "moby_id",
            "metadata_field": "moby_metadata",
        },
        MetadataSource.SS: {
            "handler": ss_handler_rom,
            "id_field": "ss_id",
            "metadata_field": "ss_metadata",
        },
        MetadataSource.RA: {
            "handler": ra_handler_rom,
            "id_field": "ra_id",
            "metadata_field": "ra_metadata",
        },
        MetadataSource.LAUNCHBOX: {
            "handler": launchbox_handler_rom,
            "id_field": "launchbox_id",
            "metadata_field": "launchbox_metadata",
        },
        MetadataSource.HASHEOUS: {
            "handler": hasheous_handler_rom,
            "id_field": "hasheous_id",
            "metadata_field": "hasheous_metadata",
        },
        MetadataSource.FLASHPOINT: {
            "handler": flashpoint_handler_rom,
            "id_field": "flashpoint_id",
            "metadata_field": "flashpoint_metadata",
        },
        MetadataSource.HLTB: {
            "handler": hltb_handler_rom,
            "id_field": "hltb_id",
            "metadata_field": "hltb_metadata",
        },
        MetadataSource.GAMELIST: {
            "handler": gamelist_handler_rom,
            "id_field": "gamelist_id",
            "metadata_field": "gamelist_metadata",
        },
        MetadataSource.LIBRETRO: {
            "handler": libretro_handler_rom,
            "id_field": "libretro_id",
            "metadata_field": None,
        },
        MetadataSource.SGDB: {
            "handler": {},
            "id_field": "sgdb_id",
            "metadata_field": None,
        },
        MetadataSource.TGDB: {
            "handler": {},
            "id_field": "tgdb_id",
            "metadata_field": None,
        },
    }

    # For COMPLETE rescans, explicitly clear metadata IDs and metadata for unselected sources
    # This ensures that when a source is no longer selected, its data is removed from the ROM
    if not newly_added and scan_type == ScanType.COMPLETE:
        for source, fields in metadata_handlers.items():
            if source not in metadata_sources:
                rom_attrs[fields["id_field"]] = None
                if fields["metadata_field"]:
                    rom_attrs[fields["metadata_field"]] = {}

        # Reset artwork fields so stale values are cleared when no source supplies them
        rom_attrs.update(
            {
                "url_cover": "",
                "url_screenshots": [],
                "url_manual": "",
                "path_cover_s": "",
                "path_cover_l": "",
                "path_screenshots": [],
                "path_manual": "",
            }
        )

    # Determine which metadata sources are available
    available_sources = [
        name
        for name, fields in metadata_handlers.items()
        if fields["handler"].get(fields["id_field"])
    ]

    # Apply metadata priority order
    priority_ordered = get_priority_ordered_metadata_sources(
        available_sources, "metadata"
    )
    # Reverse priority order to apply highest priority last
    for source_name in reversed(priority_ordered):
        handler_data = metadata_handlers[source_name]["handler"]
        # Only update fields that have valid values
        for key, field_value in handler_data.items():
            if field_value:
                rom_attrs[key] = field_value

    # Artwork sources are prioritized separately, and each field can carry its
    # own override on top of the shared artwork priority.
    for field in ["url_cover", "url_screenshots", "url_manual"]:
        priority_ordered_artwork = get_priority_ordered_metadata_sources(
            available_sources, field
        )
        # Reverse priority order to apply highest priority last
        for source_name in reversed(priority_ordered_artwork):
            # Only update fields that have valid values
            field_value = metadata_handlers[source_name]["handler"].get(field)
            if field_value:
                rom_attrs[field] = field_value

    # Don't overwrite existing base fields on update and unmatched scans
    if not newly_added and (
        scan_type == ScanType.UNMATCHED or scan_type == ScanType.UPDATE
    ):
        # A ROM's name defaults to a filename-derived placeholder when first
        # created. Treat that placeholder as "no name" so a freshly matched provider
        # name replaces it (while preserving user-edited names).
        fs_name_no_tags = fs_rom_handler.get_file_name_with_no_tags(
            rom_attrs["fs_name"]
        )
        # Both the existing name and the seeded rom_attrs name can hold the
        # placeholder. Discard either when it's a placeholder so the parsed
        # filename fallback can win.
        placeholders = (None, "", rom.fs_name, fs_name_no_tags)
        existing_name = None if rom.name in placeholders else rom.name
        matched_name = rom_attrs.get("name")
        matched_name = None if matched_name in placeholders else matched_name
        rom_attrs.update(
            {
                "name": existing_name or matched_name or fs_name_no_tags or None,
                "summary": rom.summary or rom_attrs.get("summary") or None,
                # Don't overwrite existing manually uploaded cover image
                "url_cover": (
                    rom.url_cover
                    if rom.path_cover_s
                    else rom_attrs.get("url_cover") or None
                ),
                "url_manual": rom.url_manual or rom_attrs.get("url_manual") or None,
                "url_screenshots": rom.url_screenshots
                or rom_attrs.get("url_screenshots")
                or [],
            }
        )

    # Use PICO-8 cartridge PNG as cover art if no cover is set.
    # PICO-8 .p8.png files are valid PNG images whose visual content is the
    # cartridge label, so the ROM file itself serves as the cover art.
    if not rom_attrs.get("url_cover") and not rom_attrs.get("path_cover_s"):
        pico8_url = fs_rom_handler.get_pico8_cover_url(
            platform.slug, rom_attrs["fs_name"], rom_attrs["fs_path"]
        )
        if pico8_url:
            rom_attrs["url_cover"] = pico8_url

    # If not found in any metadata source, we return the rom with the default values
    if (
        not rom_attrs.get("igdb_id")
        and not rom_attrs.get("moby_id")
        and not rom_attrs.get("ss_id")
        and not rom_attrs.get("ra_id")
        and not rom_attrs.get("launchbox_id")
        and not rom_attrs.get("hasheous_id")
        and not rom_attrs.get("flashpoint_id")
        and not rom_attrs.get("hltb_id")
        and not rom_attrs.get("gamelist_id")
    ):
        log.warning(
            f"{hl(rom_attrs['fs_name'])} not identified {emoji.EMOJI_CROSS_MARK}",
            extra=LOGGER_MODULE_NAME,
        )
        return Rom(**rom_attrs)

    async def fetch_sgdb_details(playmatch_rom: PlaymatchRomMatch) -> SGDBRom:
        """Fetch SteamGridDB details for the ROM."""
        if MetadataSource.SGDB in metadata_sources and (
            newly_added
            or scan_type == ScanType.COMPLETE
            or (scan_type == ScanType.UPDATE and rom.sgdb_id)
            or (scan_type == ScanType.UNMATCHED and not rom.sgdb_id)
        ):
            if scan_type == ScanType.UPDATE and rom.sgdb_id:
                return await meta_sgdb_handler.get_rom_by_id(rom.sgdb_id)

            if playmatch_rom["sgdb_id"] is not None:
                log.debug(
                    f"{hl(rom_attrs['fs_name'])} identified by Playmatch as SteamGridDB "
                    f"{hl(str(playmatch_rom['sgdb_id']), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_sgdb_handler.get_rom_by_id(playmatch_rom["sgdb_id"])

            file_name_no_tags = fs_rom_handler.get_file_name_with_no_tags(
                str(rom_attrs["fs_name"])
            )
            game_names = [
                igdb_handler_rom.get("name", None),
                hasheous_handler_rom.get("name", None),
                ss_handler_rom.get("name", None),
                moby_handler_rom.get("name", None),
                launchbox_handler_rom.get("name", None),
                gamelist_handler_rom.get("name", None),
                file_name_no_tags,
            ]
            valid_names = [name for name in game_names if name]
            return await meta_sgdb_handler.get_details_by_names(valid_names)

        return SGDBRom(sgdb_id=None)

    sgdb_hander_rom = await fetch_sgdb_details(playmatch_hash_match)
    if sgdb_hander_rom.get("sgdb_id"):
        rom_attrs["sgdb_id"] = sgdb_hander_rom["sgdb_id"]

        # Apply SGDB's cover only when it outranks every other source that
        # already produced one under the cover priority, and never over a
        # manually uploaded cover preserved by the UNMATCHED/UPDATE block above.
        sgdb_cover = sgdb_hander_rom.get("url_cover")
        manual_cover_preserved = (
            not newly_added
            and scan_type in (ScanType.UNMATCHED, ScanType.UPDATE)
            and rom.path_cover_s
        )
        if sgdb_cover and not manual_cover_preserved:
            cover_sources = [
                name
                for name, fields in metadata_handlers.items()
                if fields["handler"].get("url_cover")
            ]
            ranked = get_priority_ordered_metadata_sources(
                cover_sources + [MetadataSource.SGDB], "url_cover"
            )
            if ranked[0] == MetadataSource.SGDB:
                rom_attrs["url_cover"] = sgdb_cover

    log.info(
        f"{hl(rom_attrs['fs_name'])} identified as {hl(rom_attrs['name'], color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
        extra=LOGGER_MODULE_NAME,
    )

    if fs_rom["nested"]:
        for file in fs_rom["files"]:
            log.info(
                f"\t · {hl(file.file_name, color=LIGHTYELLOW)}",
                extra=LOGGER_MODULE_NAME,
            )

    rom_attrs["missing_from_fs"] = False
    return Rom(**rom_attrs)


async def _scan_asset(file_name: str, asset_path: str, should_hash: bool = False):
    file_path = f"{asset_path}/{file_name}"
    file_size = await fs_asset_handler.get_file_size(file_path)

    result = {
        "file_path": asset_path,
        "file_name": file_name,
        "file_size_bytes": file_size,
    }

    if should_hash:
        result["content_hash"] = await fs_asset_handler.compute_content_hash(file_path)

    return result


async def scan_save(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
    emulator: str | None = None,
) -> Save:
    saves_path = fs_asset_handler.build_saves_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id, emulator=emulator
    )
    scanned_asset = await _scan_asset(file_name, saves_path, should_hash=True)
    return Save(**scanned_asset)


async def scan_state(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
    emulator: str | None = None,
) -> State:
    states_path = fs_asset_handler.build_states_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id, emulator=emulator
    )
    scanned_asset = await _scan_asset(file_name, states_path)
    return State(**scanned_asset)


async def scan_memory_card_version(
    file_name: str,
    user: User,
    emulator: str,
    card_id: int,
) -> MemoryCardVersion:
    cards_path = fs_asset_handler.build_memory_cards_file_path(
        user=user, emulator=emulator, card_id=card_id
    )
    scanned_asset = await _scan_asset(file_name, cards_path, should_hash=True)
    return MemoryCardVersion(**scanned_asset, memory_card_id=card_id)


async def scan_screenshot(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
) -> Screenshot:
    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id
    )
    scanned_asset = await _scan_asset(file_name, screenshots_path)
    return Screenshot(**scanned_asset)
