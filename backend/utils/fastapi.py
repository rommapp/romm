import emoji
from typing import Any

from handler import igdbh
from utils import fs, parse_tags, get_file_extension, get_file_name_with_no_tags
from config import (
    SAVES_FOLDER_NAME,
    STATES_FOLDER_NAME,
    BIOS_FOLDER_NAME,
    SCREENSHOTS_FOLDER_NAME,
)
from config.config_loader import config
from models import Platform, Rom, Save, State, Bios, Screenshot
from logger.logger import log


def scan_platform(fs_slug: str) -> Platform:
    """Get platform details

    Args:
        fs_slug: short name of the platform
    Returns
        Platform object
    """

    log.info(f"· {fs_slug}")

    platform_attrs: dict[str, Any] = {}
    platform_attrs["fs_slug"] = fs_slug

    try:
        if fs_slug in config["PLATFORMS_BINDING"].keys():
            platform_attrs["slug"] = config["PLATFORMS_BINDING"][fs_slug]
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
    reg, rev, other_tags = parse_tags(rom_attrs["file_name"])
    rom_attrs.update(
        {
            "file_path": roms_path,
            "file_name": rom_attrs["file_name"],
            "file_name_no_tags": get_file_name_with_no_tags(rom_attrs["file_name"]),
            "file_extension": get_file_extension(rom_attrs["file_name"]),
            "file_size": file_size,
            "file_size_units": file_size_units,
            "multi": rom_attrs["multi"],
            "region": reg,
            "revision": rev,
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


def scan_save(platform: Platform, file_name: str) -> Save:
    saves_path = fs.get_fs_structure(platform.fs_slug, folder=SAVES_FOLDER_NAME)
    return Save(**_scan_asset(file_name, saves_path))


def scan_state(platform: Platform, file_name: str) -> State:
    states_path = fs.get_fs_structure(platform.fs_slug, folder=STATES_FOLDER_NAME)
    return State(**_scan_asset(file_name, states_path))


def scan_bios(platform: Platform, file_name: str) -> State:
    bios_path = fs.get_fs_structure(platform.fs_slug, folder=BIOS_FOLDER_NAME)
    return Bios(**_scan_asset(file_name, bios_path))


def scan_screenshot(file_name: str) -> State:
    return Screenshot(**_scan_asset(file_name, SCREENSHOTS_FOLDER_NAME))
