import asyncio
import zlib
from enum import Enum
from typing import Any

import emoji
from config.config_manager import config_manager as cm
from handler.database import db_platform_handler
from handler.filesystem import fs_asset_handler, fs_firmware_handler, fs_rom_handler
from handler.filesystem.roms_handler import FSRom
from handler.metadata import meta_igdb_handler, meta_moby_handler
from handler.metadata.igdb_handler import IGDBPlatform, IGDBRom
from handler.metadata.moby_handler import MobyGamesPlatform, MobyGamesRom
from logger.formatter import BLUE, RED
from logger.formatter import highlight as hl
from logger.logger import log
from models.assets import Save, Screenshot, State
from models.firmware import Firmware
from models.platform import Platform
from models.rom import Rom
from models.user import User

NON_HASHABLE_PLATFORMS = frozenset(
    (
        "amazon-alexa",
        "amazon-fire-tv",
        "android",
        "gear-vr",
        "ios",
        "ipad",
        "linux",
        "mac",
        "meta-quest-2",
        "meta-quest-3",
        "oculus-go",
        "oculus-quest",
        "oculus-rift",
        "pc",
        "ps3",
        "ps4",
        "ps4--1",
        "ps5",
        "psvr",
        "psvr2",
        "series-x",
        "switch",
        "wiiu",
        "win",
        "xbox-360",
        "xboxone",
    )
)


class ScanType(Enum):
    NEW_PLATFORMS = "new_platforms"
    QUICK = "quick"
    UNIDENTIFIED = "unidentified"
    PARTIAL = "partial"
    COMPLETE = "complete"
    HASHES = "hashes"


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

    log.info(f"· {hl(fs_slug)}")

    if metadata_sources is None:
        metadata_sources = ["igdb", "moby"]

    platform_attrs: dict[str, Any] = {}
    platform_attrs["fs_slug"] = fs_slug

    cnfg = cm.get_config()
    swapped_platform_bindings = {v: k for k, v in cnfg.PLATFORMS_BINDING.items()}

    # Sometimes users change the name of the folder, so we try to match it with the config
    if fs_slug not in fs_platforms:
        log.warning(
            f"  {fs_slug} not found in file system, trying to match via config..."
        )
        if fs_slug in swapped_platform_bindings.keys():
            platform = db_platform_handler.get_platform_by_fs_slug(fs_slug)
            if platform:
                platform_attrs["fs_slug"] = swapped_platform_bindings[platform.slug]

    try:
        if fs_slug in cnfg.PLATFORMS_BINDING.keys():
            platform_attrs["slug"] = cnfg.PLATFORMS_BINDING[fs_slug]
        else:
            platform_attrs["slug"] = fs_slug
    except (KeyError, TypeError, AttributeError):
        platform_attrs["slug"] = fs_slug

    igdb_platform = (
        (await meta_igdb_handler.get_platform(platform_attrs["slug"]))
        if "igdb" in metadata_sources
        else IGDBPlatform(igdb_id=None, slug=platform_attrs["slug"])
    )
    moby_platform = (
        meta_moby_handler.get_platform(platform_attrs["slug"])
        if "moby" in metadata_sources
        else MobyGamesPlatform(moby_id=None, slug=platform_attrs["slug"])
    )

    platform_attrs["name"] = platform_attrs["slug"].replace("-", " ").title()
    platform_attrs.update({**moby_platform, **igdb_platform})  # Reverse order

    if platform_attrs["igdb_id"] or platform_attrs["moby_id"]:
        log.info(
            emoji.emojize(
                f"  Identified as {hl(platform_attrs['name'], color=BLUE)} :video_game:"
            )
        )
    else:
        log.warning(
            emoji.emojize(f" {platform_attrs['slug']} not identified :cross_mark:")
        )

    return Platform(**platform_attrs)


def scan_firmware(
    platform: Platform,
    file_name: str,
    firmware: Firmware | None = None,
) -> Firmware:
    firmware_path = fs_firmware_handler.get_firmware_fs_structure(platform.fs_slug)

    log.info(f"\t · {file_name}")

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
        metadata_sources = ["igdb", "moby"]

    roms_path = fs_rom_handler.get_roms_fs_structure(platform.fs_slug)

    log.info(f"\t · {hl(fs_rom['file_name'])}")

    if fs_rom.get("multi", False):
        for file in fs_rom["files"]:
            log.info(f"\t\t · {file['filename']}")

    # Set default properties
    rom_attrs = {
        **fs_rom,
        "id": rom.id if rom else None,
        "platform_id": platform.id,
        "name": fs_rom["file_name"],
        "url_cover": "",
        "url_screenshots": [],
    }

    # Update properties from existing rom if not a complete rescan
    if rom and scan_type != ScanType.COMPLETE:
        rom_attrs.update(
            {
                "igdb_id": rom.igdb_id,
                "moby_id": rom.moby_id,
                "sgdb_id": rom.sgdb_id,
                "name": rom.name,
                "slug": rom.slug,
                "summary": rom.summary,
                "igdb_metadata": rom.igdb_metadata,
                "moby_metadata": rom.moby_metadata,
                "url_cover": rom.url_cover,
                "path_cover_s": rom.path_cover_s,
                "path_cover_l": rom.path_cover_l,
                "path_screenshots": rom.path_screenshots,
                "url_screenshots": rom.url_screenshots,
            }
        )

    # Update properties that don't require metadata
    file_size = sum([file["size"] for file in rom_attrs["files"]])
    regs, rev, langs, other_tags = fs_rom_handler.parse_tags(rom_attrs["file_name"])
    rom_attrs.update(
        {
            "file_path": roms_path,
            "file_name": rom_attrs["file_name"],
            "file_name_no_tags": fs_rom_handler.get_file_name_with_no_tags(
                rom_attrs["file_name"]
            ),
            "file_name_no_ext": fs_rom_handler.get_file_name_with_no_extension(
                rom_attrs["file_name"]
            ),
            "file_extension": fs_rom_handler.parse_file_extension(
                rom_attrs["file_name"]
            ),
            "file_size_bytes": file_size,
            "multi": rom_attrs["multi"],
            "regions": regs,
            "revision": rev,
            "languages": langs,
            "tags": other_tags,
        }
    )

    # Calculating hashes is expensive, so we only do it if necessary
    if not rom or scan_type == ScanType.COMPLETE or scan_type == ScanType.HASHES:
        # Skip hashing games for platforms that don't have a hash database
        if platform.slug in NON_HASHABLE_PLATFORMS:
            rom_attrs.update({"crc_hash": "", "md5_hash": "", "sha1_hash": ""})
        else:
            try:
                rom_hashes = fs_rom_handler.get_rom_hashes(
                    rom_attrs["file_name"], roms_path
                )
                rom_attrs.update(**rom_hashes)
            except zlib.error as e:
                # Return empty hashes if calculating them fails for corrupted files
                log.error(
                    f"Hashes of {rom_attrs['file_name']} couldn't be calculated: {hl(str(e), color=RED)}"
                )
                rom_attrs.update({"crc_hash": "", "md5_hash": "", "sha1_hash": ""})

    # If no metadata scan is required
    if scan_type == ScanType.HASHES:
        return Rom(**rom_attrs)

    async def fetch_igdb_rom():
        if (
            "igdb" in metadata_sources
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
                rom_attrs["file_name"], main_platform_igdb_id
            )

        return IGDBRom(igdb_id=None)

    async def fetch_moby_rom():
        if (
            "moby" in metadata_sources
            and platform.moby_id
            and (
                not rom
                or scan_type == ScanType.COMPLETE
                or (scan_type == ScanType.PARTIAL and not rom.moby_id)
                or (scan_type == ScanType.UNIDENTIFIED and not rom.moby_id)
            )
        ):
            return await meta_moby_handler.get_rom(
                rom_attrs["file_name"], platform_moby_id=platform.moby_id
            )

        return MobyGamesRom(moby_id=None)

    # Run both metadata fetches concurrently
    igdb_handler_rom, moby_handler_rom = await asyncio.gather(
        fetch_igdb_rom(), fetch_moby_rom()
    )

    # Reversed to prioritize IGDB
    rom_attrs.update({**moby_handler_rom, **igdb_handler_rom})

    # If not found in IGDB or MobyGames
    if not igdb_handler_rom.get("igdb_id") and not moby_handler_rom.get("moby_id"):
        log.warning(
            emoji.emojize(f"\t   {rom_attrs['file_name']} not identified :cross_mark:")
        )
        return Rom(**rom_attrs)

    log.info(emoji.emojize(f"\t   Identified as {rom_attrs['name']} :alien_monster:"))

    return Rom(**rom_attrs)


def _scan_asset(file_name: str, path: str):
    log.info(f"\t\t · {file_name}")

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
    file_name: str, user: User, platform_fs_slug: str, emulator: str | None = None
) -> Save:
    saves_path = fs_asset_handler.build_saves_file_path(
        user=user, platform_fs_slug=platform_fs_slug, emulator=emulator
    )
    return Save(**_scan_asset(file_name, saves_path))


def scan_state(
    file_name: str, user: User, platform_fs_slug: str, emulator: str | None = None
) -> State:
    states_path = fs_asset_handler.build_states_file_path(
        user=user, platform_fs_slug=platform_fs_slug, emulator=emulator
    )
    return State(**_scan_asset(file_name, states_path))


def scan_screenshot(
    file_name: str,
    user: User,
    platform_fs_slug: str,
) -> Screenshot:
    screenshots_path = fs_asset_handler.build_screenshots_file_path(
        user=user, platform_fs_slug=platform_fs_slug
    )
    return Screenshot(**_scan_asset(file_name, screenshots_path))
