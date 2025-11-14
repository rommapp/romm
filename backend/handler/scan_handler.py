import asyncio
import enum
from typing import Any

import socketio  # type: ignore

from config.config_manager import config_manager as cm
from endpoints.responses.rom import SimpleRomSchema
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_asset_handler, fs_firmware_handler
from handler.filesystem.roms_handler import FSRom
from handler.metadata import (
    meta_flashpoint_handler,
    meta_gamelist_handler,
    meta_hasheous_handler,
    meta_hltb_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
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
from handler.metadata.launchbox_handler import LAUNCHBOX_PLATFORM_LIST, LaunchboxRom
from handler.metadata.moby_handler import MOBYGAMES_PLATFORM_LIST, MobyGamesRom
from handler.metadata.playmatch_handler import PlaymatchRomMatch
from handler.metadata.ra_handler import RA_PLATFORM_LIST, RAGameRom
from handler.metadata.sgdb_handler import SGDBRom
from handler.metadata.ss_handler import SCREENSAVER_PLATFORM_LIST, SSRom
from logger.formatter import BLUE, LIGHTYELLOW
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save, Screenshot, State
from models.firmware import Firmware
from models.platform import Platform
from models.rom import Rom
from models.user import User
from utils import emoji

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
        priority_type: Type of priority to use ("metadata" or "artwork")

    Returns:
        List of metadata sources ordered by priority
    """
    cnfg = cm.get_config()

    if priority_type == "metadata":
        priority_order = cnfg.SCAN_METADATA_PRIORITY
    else:
        priority_order = cnfg.SCAN_ARTWORK_PRIORITY

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

    platform_attrs["name"] = platform_attrs["slug"].replace("-", " ").title()
    platform_attrs.update(
        {
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
            "file_name_no_tags": fs_firmware_handler.get_file_name_with_no_tags(
                file_name
            ),
            "file_name_no_ext": fs_firmware_handler.get_file_name_with_no_extension(
                file_name
            ),
            "file_extension": fs_firmware_handler.parse_file_extension(file_name),
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
    socket_manager: socketio.AsyncRedisManager | None = None,
) -> Rom:
    rom_attrs = {
        "id": rom.id,
        "platform_id": platform.id,
        "fs_name": fs_rom["fs_name"],
        "fs_path": rom.fs_path,
        "fs_name_no_tags": rom.fs_name_no_tags,
        "fs_name_no_ext": rom.fs_name_no_ext,
        "fs_extension": rom.fs_extension,
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

    async def fetch_playmatch_hash_match() -> PlaymatchRomMatch:
        if (
            MetadataSource.IGDB in metadata_sources
            and platform.igdb_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.igdb_id)
                or (scan_type == ScanType.UNMATCHED and not rom.igdb_id)
            )
        ):
            return await meta_playmatch_handler.lookup_rom(fs_rom["files"])

        return PlaymatchRomMatch(igdb_id=None)

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
                    and not rom.hasheous_id
                    and rom.platform_slug in HASHEOUS_PLATFORM_LIST
                )
            )
        ):
            return await meta_hasheous_handler.lookup_rom(
                platform.slug, fs_rom["files"]
            )

        return HasheousRom(hasheous_id=None, igdb_id=None, tgdb_id=None, ra_id=None)

    _added_rom = db_rom_handler.add_rom(Rom(**rom_attrs))
    _added_rom.is_identifying = True

    if socket_manager:
        await socket_manager.emit(
            "scan:scanning_rom",
            {
                **SimpleRomSchema.from_orm_with_factory(_added_rom).model_dump(
                    exclude={"created_at", "updated_at", "rom_user"}
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
                    and not rom.igdb_id
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
                return await meta_igdb_handler.get_rom_by_id(h_igdb_id)

            # Use Playmatch matches to get the IGDB ID
            if playmatch_rom["igdb_id"] is not None:
                log.debug(
                    f"{hl(rom_attrs['fs_name'])} identified by Playmatch as "
                    f"{hl(str(playmatch_rom["igdb_id"]), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )

                return await meta_igdb_handler.get_rom_by_id(playmatch_rom["igdb_id"])

            main_platform_igdb_id = get_main_platform_igdb_id(platform)
            if scan_type == ScanType.UPDATE and rom.igdb_id:
                # Use the ID to refetch the metadata from IGDB
                return await meta_igdb_handler.get_rom_by_id(rom.igdb_id)
            else:
                # If no matches found, use the file name to get the IGDB ID
                return await meta_igdb_handler.get_rom(
                    rom_attrs["fs_name"], main_platform_igdb_id or platform.igdb_id
                )

        return IGDBRom(igdb_id=None)

    async def fetch_gamelist_rom() -> GamelistRom:
        if MetadataSource.GAMELIST in metadata_sources and (
            newly_added
            or scan_type == ScanType.COMPLETE
            or (scan_type == ScanType.UPDATE and rom.gamelist_id)
            or (scan_type == ScanType.UNMATCHED and not rom.gamelist_id)
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
                    and not rom.flashpoint_id
                    and platform.slug in FLASHPOINT_PLATFORM_LIST
                )
            )
        ):
            if scan_type == ScanType.UPDATE and rom.flashpoint_id:
                return await meta_flashpoint_handler.get_rom_by_id(rom.flashpoint_id)
            else:
                return await meta_flashpoint_handler.get_rom(
                    rom_attrs["fs_name"], platform.slug
                )

        return FlashpointRom(flashpoint_id=None)

    async def fetch_hltb_rom() -> HLTBRom:
        if (
            MetadataSource.HLTB in metadata_sources
            and platform.slug in HLTB_PLATFORM_LIST
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.hltb_id)
                or (scan_type == ScanType.UNMATCHED and not rom.hltb_id)
            )
        ):
            search_input = rom.name or rom_attrs["fs_name_no_tags"]
            return await meta_hltb_handler.get_rom(search_input, platform.slug)

        return HLTBRom(hltb_id=None)

    async def fetch_moby_rom() -> MobyGamesRom:
        if (
            MetadataSource.MOBY in metadata_sources
            and platform.moby_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.moby_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and not rom.moby_id
                    and rom.platform_slug in MOBYGAMES_PLATFORM_LIST
                )
            )
        ):
            if scan_type == ScanType.UPDATE and rom.moby_id:
                return await meta_moby_handler.get_rom_by_id(rom.moby_id)
            else:
                return await meta_moby_handler.get_rom(
                    rom_attrs["fs_name"], platform_moby_id=platform.moby_id
                )

        return MobyGamesRom(moby_id=None)

    async def fetch_ss_rom() -> SSRom:
        if (
            MetadataSource.SS in metadata_sources
            and platform.ss_id
            and (
                newly_added
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.UPDATE and rom.ss_id)
                or (
                    scan_type == ScanType.UNMATCHED
                    and not rom.ss_id
                    and rom.platform_slug in SCREENSAVER_PLATFORM_LIST
                )
            )
        ):
            # Use the ID to refetch metadata
            if scan_type == ScanType.UPDATE and rom.ss_id:
                return await meta_ss_handler.get_rom_by_id(rom, rom.ss_id)

            # Use the file hashes for lookup
            game_by_hash = await meta_ss_handler.lookup_rom(
                rom, platform.ss_id, fs_rom["files"]
            )
            if game_by_hash.get("ss_id"):
                return game_by_hash

            # Fallback to the filename
            return await meta_ss_handler.get_rom(
                rom, rom_attrs["fs_name"], platform_ss_id=platform.ss_id
            )

        return SSRom(ss_id=None)

    async def fetch_launchbox_rom(platform_slug: str) -> LaunchboxRom:
        if MetadataSource.LAUNCHBOX in metadata_sources and (
            newly_added
            or scan_type == ScanType.COMPLETE
            or (scan_type == ScanType.UPDATE and rom.launchbox_id)
            or (
                scan_type == ScanType.UNMATCHED
                and not rom.launchbox_id
                and rom.platform_slug in LAUNCHBOX_PLATFORM_LIST
            )
        ):
            if scan_type == ScanType.UPDATE and rom.launchbox_id:
                return await meta_launchbox_handler.get_rom_by_id(rom.launchbox_id)
            else:
                return await meta_launchbox_handler.get_rom(
                    rom_attrs["fs_name"], platform_slug
                )

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
                    and not rom.ra_id
                    and rom.platform_slug in RA_PLATFORM_LIST
                )
            )
        ):
            # Use Hasheous match to get the IGDB ID
            h_ra_id = hasheous_rom.get("ra_id")
            if h_ra_id:
                log.debug(
                    f"{hl(rom_attrs['fs_name'])} identified by Hasheous as "
                    f"{hl(str(h_ra_id), color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
                    extra=LOGGER_MODULE_NAME,
                )
                return await meta_ra_handler.get_rom_by_id(rom=rom, ra_id=h_ra_id)

            if scan_type == ScanType.UPDATE and rom.ra_id:
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
                    and not rom.hasheous_id
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

    # Run metadata fetches concurrently
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
    ) = await asyncio.gather(
        fetch_igdb_rom(playmatch_hash_match, hasheous_hash_match),
        fetch_moby_rom(),
        fetch_ss_rom(),
        fetch_ra_rom(hasheous_hash_match),
        fetch_launchbox_rom(platform.slug),
        fetch_hasheous_rom(hasheous_hash_match),
        fetch_flashpoint_rom(),
        fetch_hltb_rom(),
        fetch_gamelist_rom(),
    )

    metadata_handlers = {
        MetadataSource.IGDB: igdb_handler_rom,
        MetadataSource.MOBY: moby_handler_rom,
        MetadataSource.SS: ss_handler_rom,
        MetadataSource.RA: ra_handler_rom,
        MetadataSource.LAUNCHBOX: launchbox_handler_rom,
        MetadataSource.HASHEOUS: hasheous_handler_rom,
        MetadataSource.FLASHPOINT: flashpoint_handler_rom,
        MetadataSource.HLTB: hltb_handler_rom,
        MetadataSource.GAMELIST: gamelist_handler_rom,
    }

    # Determine which metadata sources are available
    available_sources = [
        name for name, handler in metadata_handlers.items() if handler.get(f"{name}_id")
    ]

    # Apply metadata priority order
    priority_ordered = get_priority_ordered_metadata_sources(
        available_sources, "metadata"
    )
    # Reverse priority order to apply highest priority last
    for source_name in reversed(priority_ordered):
        handler_data = metadata_handlers[source_name]
        # Only update fields that have valid values
        for key, field_value in handler_data.items():
            if field_value:
                rom_attrs[key] = field_value

    # Artwork sources are prioritized separately
    priority_ordered_artwork = get_priority_ordered_metadata_sources(
        available_sources, "artwork"
    )
    # Reverse priority order to apply highest priority last
    for source_name in reversed(priority_ordered_artwork):
        handler_data = metadata_handlers[source_name]
        for field in ["url_cover", "url_screenshots", "url_manual"]:
            # Only update fields that have valid values
            field_value = handler_data.get(field)
            if field_value:
                rom_attrs[field] = field_value

    # Don't overwrite existing base fields on update and unmatched scans
    if not newly_added and (
        scan_type == ScanType.UNMATCHED or scan_type == ScanType.UPDATE
    ):
        rom_attrs.update(
            {
                "name": rom.name or rom_attrs.get("name") or None,
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

    async def fetch_sgdb_details() -> SGDBRom:
        """Fetch SteamGridDB details for the ROM."""
        if MetadataSource.SGDB in metadata_sources and (
            newly_added
            or scan_type == ScanType.COMPLETE
            or (scan_type == ScanType.UPDATE and rom.sgdb_id)
            or (scan_type == ScanType.UNMATCHED and not rom.sgdb_id)
        ):
            if scan_type == ScanType.UPDATE and rom.sgdb_id:
                return await meta_sgdb_handler.get_rom_by_id(rom.sgdb_id)
            else:
                game_names = [
                    igdb_handler_rom.get("name", None),
                    hasheous_handler_rom.get("name", None),
                    ss_handler_rom.get("name", None),
                    moby_handler_rom.get("name", None),
                    launchbox_handler_rom.get("name", None),
                    gamelist_handler_rom.get("name", None),
                    rom_attrs["fs_name_no_tags"],
                ]
                game_names = [name for name in game_names if name]
                return await meta_sgdb_handler.get_details_by_names(game_names)

        return SGDBRom(sgdb_id=None)

    sgdb_hander_rom = await fetch_sgdb_details()
    if sgdb_hander_rom.get("sgdb_id"):
        rom_attrs.update({**sgdb_hander_rom})

    log.info(
        f"{hl(rom_attrs['fs_name'])} identified as {hl(rom_attrs['name'], color=BLUE)} {emoji.EMOJI_ALIEN_MONSTER}",
        extra=LOGGER_MODULE_NAME,
    )

    if rom.has_nested_single_file or rom.has_multiple_files:
        for file in fs_rom["files"]:
            log.info(
                f"\t · {hl(file.file_name, color=LIGHTYELLOW)}",
                extra=LOGGER_MODULE_NAME,
            )

    rom_attrs["missing_from_fs"] = False
    return Rom(**rom_attrs)


async def _scan_asset(file_name: str, asset_path: str):
    file_path = f"{asset_path}/{file_name}"
    file_size = await fs_asset_handler.get_file_size(file_path)

    return {
        "file_path": asset_path,
        "file_name": file_name,
        "file_name_no_tags": fs_asset_handler.get_file_name_with_no_tags(file_name),
        "file_name_no_ext": fs_asset_handler.get_file_name_with_no_extension(file_name),
        "file_extension": fs_asset_handler.parse_file_extension(file_name),
        "file_size_bytes": file_size,
    }


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
    scanned_asset = await _scan_asset(file_name, saves_path)
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
