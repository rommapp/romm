import asyncio
from enum import Enum
from typing import Any

import emoji
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler
from handler.filesystem import fs_asset_handler, fs_firmware_handler, fs_rom_handler
from handler.filesystem.roms_handler import FSRom
from handler.metadata import (
    meta_igdb_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_ss_handler,
)
from handler.metadata.igdb_handler import IGDBPlatform, IGDBRom
from handler.metadata.moby_handler import MobyGamesPlatform, MobyGamesRom
from handler.metadata.ra_handler import RAGameRom, RAGamesPlatform
from handler.metadata.ss_handler import SSPlatform, SSRom
from logger.formatter import BLUE, LIGHTYELLOW
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save, Screenshot, State
from models.firmware import Firmware
from models.platform import Platform
from models.rom import Rom
from models.user import User

LOGGER_MODULE_NAME = {"module_name": "scan"}


class ScanType(Enum):
    NEW_PLATFORMS = "new_platforms"
    QUICK = "quick"
    UNIDENTIFIED = "unidentified"
    PARTIAL = "partial"
    COMPLETE = "complete"
    HASHES = "hashes"


class MetadataSource:
    IGDB = "igdb"
    MOBY = "moby"
    SS = "ss"
    RA = "ra"


async def fetch_ra_info(
    platform: Platform,
    rom_id: int,
    hash: str,
) -> RAGameRom:

    return await meta_ra_handler.get_rom(
        platform=platform,
        rom_id=rom_id,
        hash=hash,
    )


async def _get_main_platform_igdb_id(platform: Platform):
    cnfg = cm.get_config()

    if platform.fs_slug in cnfg.PLATFORMS_VERSIONS.keys():
        main_platform_slug = cnfg.PLATFORMS_VERSIONS[platform.fs_slug]
        main_platform = db_platform_handler.get_platform_by_fs_slug(main_platform_slug)
        if main_platform:
            main_platform_igdb_id = main_platform.igdb_id
        else:
            main_platform_igdb_id = (
                await meta_igdb_handler.get_platform(main_platform_slug)
            )["igdb_id"]
            if not main_platform_igdb_id:
                main_platform_igdb_id = platform.igdb_id
    else:
        main_platform_igdb_id = platform.igdb_id
    return main_platform_igdb_id


async def scan_platform(
    fs_slug: str,
    fs_platforms: list[str],
    metadata_sources: list[str] | None = None,
) -> Platform:
    """Get platform details

    Args:
        fs_slug: short name of the platform
    Returns
        Platform object
    """

    if metadata_sources is None:
        metadata_sources = [
            MetadataSource.IGDB,
            MetadataSource.MOBY,
            MetadataSource.SS,
            MetadataSource.RA,
        ]

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
    igdb_platform = (
        (await meta_igdb_handler.get_platform(platform_attrs["slug"]))
        if MetadataSource.IGDB in metadata_sources
        else IGDBPlatform(igdb_id=None, slug=platform_attrs["slug"])
    )
    moby_platform = (
        meta_moby_handler.get_platform(platform_attrs["slug"])
        if MetadataSource.MOBY in metadata_sources
        else MobyGamesPlatform(moby_id=None, slug=platform_attrs["slug"])
    )
    ss_platform = (
        meta_ss_handler.get_platform(platform_attrs["slug"])
        if MetadataSource.SS in metadata_sources
        else SSPlatform(ss_id=None, slug=platform_attrs["slug"])
    )

    ra_platform = (
        meta_ra_handler.get_platform(platform_attrs["slug"])
        if MetadataSource.RA in metadata_sources
        else RAGamesPlatform(ra_id=None, slug=platform_attrs["slug"])
    )

    platform_attrs["name"] = platform_attrs["slug"].replace("-", " ").title()
    platform_attrs.update(
        {**ra_platform, **moby_platform, **ss_platform, **igdb_platform}
    )  # Reverse order

    if (
        platform_attrs["igdb_id"]
        or platform_attrs["moby_id"]
        or platform_attrs["ss_id"]
    ):
        log.info(
            emoji.emojize(
                f"Folder {hl(platform_attrs['slug'])}[{hl(fs_slug, color=LIGHTYELLOW)}] identified as {hl(platform_attrs['name'], color=BLUE)} :video_game:"
            ),
            extra={"module_name": "scan"},
        )
    else:
        log.warning(
            emoji.emojize(
                f"Platform {hl(platform_attrs['slug'])} not identified :cross_mark:"
            ),
            extra=LOGGER_MODULE_NAME,
        )

    return Platform(**platform_attrs)


def scan_firmware(
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

    file_size = fs_firmware_handler.get_firmware_file_size(
        firmware_path=firmware_path,
        file_name=file_name,
    )

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

    file_hashes = fs_firmware_handler.calculate_file_hashes(
        firmware_path=firmware_path,
        file_name=file_name,
    )

    firmware_attrs.update(**file_hashes)

    return Firmware(**firmware_attrs)


async def scan_rom(
    platform: Platform,
    fs_rom: FSRom,
    scan_type: ScanType,
    rom: Rom | None = None,
    metadata_sources: list[str] | None = None,
) -> Rom:
    if not metadata_sources:
        metadata_sources = [
            MetadataSource.IGDB,
            MetadataSource.MOBY,
            MetadataSource.SS,
            MetadataSource.RA,
        ]

    roms_path = fs_rom_handler.get_roms_fs_structure(platform.fs_slug)

    # Set default properties
    rom_attrs = {
        "id": rom.id if rom else None,
        "multi": fs_rom["multi"],
        "fs_name": fs_rom["fs_name"],
        "platform_id": platform.id,
        "name": fs_rom["fs_name"],
        "url_cover": "",
        "url_manual": "",
        "url_screenshots": [],
    }

    # Update properties from existing rom if not a complete rescan
    if rom and scan_type != ScanType.COMPLETE:
        rom_attrs.update(
            {
                "igdb_id": rom.igdb_id,
                "moby_id": rom.moby_id,
                "ss_id": rom.ss_id,
                "sgdb_id": rom.sgdb_id,
                "ra_id": rom.ra_id,
                "name": rom.name,
                "slug": rom.slug,
                "summary": rom.summary,
                "igdb_metadata": rom.igdb_metadata,
                "moby_metadata": rom.moby_metadata,
                "url_cover": rom.url_cover,
                "url_manual": rom.url_manual,
                "path_cover_s": rom.path_cover_s,
                "path_cover_l": rom.path_cover_l,
                "path_screenshots": rom.path_screenshots,
                "url_screenshots": rom.url_screenshots,
            }
        )

    # Update properties that don't require metadata
    filesize = sum([file.file_size_bytes for file in fs_rom["files"]])
    regs, rev, langs, other_tags = fs_rom_handler.parse_tags(rom_attrs["fs_name"])
    rom_attrs.update(
        {
            "fs_path": roms_path,
            "fs_name": rom_attrs["fs_name"],
            "fs_name_no_tags": fs_rom_handler.get_file_name_with_no_tags(
                rom_attrs["fs_name"]
            ),
            "fs_name_no_ext": fs_rom_handler.get_file_name_with_no_extension(
                rom_attrs["fs_name"]
            ),
            "fs_extension": fs_rom_handler.parse_file_extension(rom_attrs["fs_name"]),
            "fs_size_bytes": filesize,
            "regions": regs,
            "revision": rev,
            "languages": langs,
            "tags": other_tags,
        }
    )

    # Set empty hashes when we plan to recalculate them
    if not rom or scan_type == ScanType.COMPLETE or scan_type == ScanType.HASHES:
        rom_attrs.update({"crc_hash": "", "md5_hash": "", "sha1_hash": ""})

    # If no metadata scan is required
    if scan_type == ScanType.HASHES:
        return Rom(**rom_attrs)

    async def fetch_igdb_rom():
        if (
            MetadataSource.IGDB in metadata_sources
            and platform.igdb_id
            and (
                not rom
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.igdb_id)
                or (scan_type == ScanType.UNIDENTIFIED and not rom.igdb_id)
            )
        ):
            main_platform_igdb_id = await _get_main_platform_igdb_id(platform)
            return await meta_igdb_handler.get_rom(
                rom_attrs["fs_name"], main_platform_igdb_id or platform.igdb_id
            )

        return IGDBRom(igdb_id=None)

    async def fetch_moby_rom():
        if (
            MetadataSource.MOBY in metadata_sources
            and platform.moby_id
            and (
                not rom
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.moby_id)
                or (scan_type == ScanType.UNIDENTIFIED and not rom.moby_id)
            )
        ):
            return await meta_moby_handler.get_rom(
                rom_attrs["fs_name"], platform_moby_id=platform.moby_id
            )

        return MobyGamesRom(moby_id=None)

    async def fetch_ss_rom():
        if (
            MetadataSource.SS in metadata_sources
            and platform.ss_id
            and (
                not rom
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.ss_id)
                or (scan_type == ScanType.UNIDENTIFIED and not rom.ss_id)
            )
        ):
            return await meta_ss_handler.get_rom(
                rom_attrs["fs_name"], platform_ss_id=platform.ss_id
            )

        return SSRom(ss_id=None)

    # Run both metadata fetches concurrently
    igdb_handler_rom, moby_handler_rom, ss_handler_rom = await asyncio.gather(
        fetch_igdb_rom(), fetch_moby_rom(), fetch_ss_rom()
    )

    if rom:
        # Only update fields if match is found
        if moby_handler_rom.get("moby_id"):
            rom_attrs.update({**moby_handler_rom})
        if ss_handler_rom.get("ss_id"):
            rom_attrs.update({**ss_handler_rom})
        if igdb_handler_rom.get("igdb_id"):
            rom_attrs.update({**igdb_handler_rom})
    else:
        # Reversed to prioritize IGDB
        rom_attrs.update({**moby_handler_rom, **ss_handler_rom, **igdb_handler_rom})

    # If not found in IGDB, MobyGames and Screenscraper
    if (
        not igdb_handler_rom.get("igdb_id")
        and not moby_handler_rom.get("moby_id")
        and not ss_handler_rom.get("ss_id")
    ):
        log.warning(
            emoji.emojize(f"{hl(rom_attrs['fs_name'])} not identified :cross_mark:"),
            extra=LOGGER_MODULE_NAME,
        )
        return Rom(**rom_attrs)

    log.info(
        emoji.emojize(
            f"{hl(rom_attrs['fs_name'])} identified as {hl(rom_attrs['name'], color=BLUE)} :alien_monster:"
        ),
        extra=LOGGER_MODULE_NAME,
    )
    if fs_rom.get("multi", False):
        for file in fs_rom["files"]:
            log.info(
                f"\t · {hl(file.file_name, color=LIGHTYELLOW)}",
                extra=LOGGER_MODULE_NAME,
            )

    return Rom(**rom_attrs)


def _scan_asset(file_name: str, path: str):
    file_size = fs_asset_handler.get_asset_size(file_name=file_name, asset_path=path)

    return {
        "file_path": path,
        "file_name": file_name,
        "file_name_no_tags": fs_asset_handler.get_file_name_with_no_tags(file_name),
        "file_name_no_ext": fs_asset_handler.get_file_name_with_no_extension(file_name),
        "file_extension": fs_asset_handler.parse_file_extension(file_name),
        "file_size_bytes": file_size,
    }


def scan_save(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
    emulator: str | None = None,
) -> Save:
    saves_path = fs_asset_handler.build_saves_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id, emulator=emulator
    )
    return Save(**_scan_asset(file_name, saves_path))


def scan_state(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
    emulator: str | None = None,
) -> State:
    states_path = fs_asset_handler.build_states_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id, emulator=emulator
    )
    return State(**_scan_asset(file_name, states_path))


def scan_screenshot(
    file_name: str,
    user: User,
    platform_fs_slug: str,
    rom_id: int,
) -> Screenshot:
    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=user, platform_fs_slug=platform_fs_slug, rom_id=rom_id
    )
    return Screenshot(**_scan_asset(file_name, screenshots_path))
