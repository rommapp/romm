import emoji
import os
from typing import Any

from handler import igdbh, dbh
from utils import fs, parse_tags, get_file_extension, get_file_name_with_no_tags
from config.config_loader import config
from models import Platform, Rom, Save, State, Screenshot
from logger.logger import log

SWAPPED_PLATFORM_BINDINGS = dict((v, k) for k, v in config.PLATFORMS_BINDING.items())


def scan_platform(fs_slug: str, fs_platforms) -> Platform:
    """Get platform details

    Args:
        fs_slug: short name of the platform
    Returns
        Platform object
    """

    log.info(f"· {fs_slug}")

    platform_attrs: dict[str, Any] = {}
    platform_attrs["fs_slug"] = fs_slug

    # Sometimes users change the name of the folder, so we try to match it with the config
    if fs_slug not in fs_platforms:
        log.warning(
            f"  {fs_slug} not found in file system, trying to match via config..."
        )
        if fs_slug in SWAPPED_PLATFORM_BINDINGS.keys():
            platform = dbh.get_platform_by_fs_slug(fs_slug)
            if platform:
                platform_attrs["fs_slug"] = SWAPPED_PLATFORM_BINDINGS[platform.slug]

    try:
        if fs_slug in config.PLATFORMS_BINDING.keys():
            platform_attrs["slug"] = config.PLATFORMS_BINDING[fs_slug]
        else:
            platform_attrs["slug"] = fs_slug
    except (KeyError, TypeError, AttributeError):
        platform_attrs["slug"] = fs_slug

    platform = igdbh.get_platform(platform_attrs["slug"])

    if platform["igdb_id"]:
        log.info(emoji.emojize(f"  Identified as {platform['name']} :video_game:"))
    else:
        log.warning(f'  {platform_attrs["slug"]} not found in IGDB')

    platform_attrs.update(platform)

    return Platform(**platform_attrs)


async def scan_rom(
    platform: Platform,
    rom_attrs: dict,
    r_igbd_id_search: str = "",
    overwrite: bool = False,
) -> Rom:
    roms_path = fs.get_fs_structure(platform.fs_slug)

    log.info(f"\t · {r_igbd_id_search or rom_attrs['file_name']}")

    if rom_attrs.get("multi", False):
        for file in rom_attrs["files"]:
            log.info(f"\t\t · {file}")

    # Update properties that don't require IGDB
    file_size, file_size_units = fs.get_rom_file_size(
        multi=rom_attrs["multi"],
        file_name=rom_attrs["file_name"],
        multi_files=rom_attrs["files"],
        roms_path=roms_path,
    )
    regs, rev, langs, other_tags = parse_tags(rom_attrs["file_name"])
    rom_attrs.update(
        {
            "file_path": roms_path,
            "file_name": rom_attrs["file_name"],
            "file_name_no_tags": get_file_name_with_no_tags(rom_attrs["file_name"]),
            "file_extension": get_file_extension(rom_attrs["file_name"]),
            "file_size": file_size,
            "file_size_units": file_size_units,
            "multi": rom_attrs["multi"],
            "regions": regs,
            "revision": rev,
            "languages": langs,
            "tags": other_tags,
        }
    )
    rom_attrs["platform_slug"] = platform.slug

    # Search in IGDB
    igdbh_rom = (
        igdbh.get_rom_by_id(int(r_igbd_id_search))
        if r_igbd_id_search
        else await igdbh.get_rom(rom_attrs["file_name"], platform.igdb_id)
    )

    rom_attrs.update(igdbh_rom)

    # Return early if not found in IGDB
    if not igdbh_rom["igdb_id"]:
        log.warning(
            f"\t   {r_igbd_id_search or rom_attrs['file_name']} not found in IGDB"
        )
        return Rom(**rom_attrs)

    log.info(emoji.emojize(f"\t   Identified as {igdbh_rom['name']} :alien_monster:"))

    # Update properties from IGDB
    rom_attrs.update(
        fs.get_rom_cover(
            overwrite=overwrite,
            fs_slug=platform.slug,
            rom_name=rom_attrs["name"],
            url_cover=rom_attrs["url_cover"],
        )
    )
    rom_attrs.update(
        fs.get_rom_screenshots(
            fs_slug=platform.slug,
            rom_name=rom_attrs["name"],
            url_screenshots=rom_attrs["url_screenshots"],
        )
    )

    return Rom(**rom_attrs)


def _scan_asset(file_name: str, path: str):
    log.info(f"\t\t · {file_name}")

    file_size = fs.get_fs_file_size(file_name=file_name, asset_path=path)

    return {
        "file_path": path,
        "file_name": file_name,
        "file_name_no_tags": get_file_name_with_no_tags(file_name),
        "file_extension": get_file_extension(file_name),
        "file_size_bytes": file_size,
    }


def scan_save(platform: Platform, emulator: str, file_name: str) -> Save:
    saves_path = fs.get_fs_structure(platform.fs_slug, folder=config.SAVES_FOLDER_NAME)
    # Scan asset with the sames path and emulator folder name
    return Save(**_scan_asset(file_name, os.path.join(saves_path, emulator)))


def scan_state(platform: Platform, emulator: str, file_name: str) -> State:
    states_path = fs.get_fs_structure(
        platform.fs_slug, folder=config.STATES_FOLDER_NAME
    )
    return State(**_scan_asset(file_name, os.path.join(states_path, emulator)))


def scan_screenshot(file_name: str) -> State:
    return Screenshot(**_scan_asset(file_name, config.SCREENSHOTS_FOLDER_NAME))
