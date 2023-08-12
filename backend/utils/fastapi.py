import emoji
from typing import Any

from handler import igdbh
from utils import fs, parse_tags, get_file_extension, get_file_name_with_no_tags
from config.config_loader import config
from models import Platform, Rom
from logger.logger import log


def scan_platform(fs_slug: str) -> Platform:
    """Get platform details

    Args:
        p_slug: short name of the platform
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
        log.warning(f"  {fs_slug} not found in IGDB")

    platform_attrs.update(platform)

    return Platform(**platform_attrs)


def scan_rom(
    platform: Platform,
    rom_attrs: dict,
    r_igbd_id_search: str = "",
    overwrite: bool = False,
) -> Rom:
    p_slug = platform.fs_slug or platform.slug or ""
    roms_path = fs.get_roms_structure(p_slug)

    log.info(f"\t · {r_igbd_id_search or rom_attrs['file_name']}")

    if rom_attrs.get("multi", False):
        for file in rom_attrs["files"]:
            log.info(f"\t\t · {file}")

    # Update properties that don't require IGDB
    file_size, file_size_units = fs.get_rom_size(
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
            "file_extension": get_file_extension(rom_attrs),
            "file_size": file_size,
            "file_size_units": file_size_units,
            "multi": rom_attrs["multi"],
            "region": reg,
            "revision": rev,
            "tags": other_tags,
        }
    )
    rom_attrs["p_igdb_id"] = platform.igdb_id
    rom_attrs["p_slug"] = platform.slug
    rom_attrs["p_name"] = platform.name

    # Search in IGDB
    igdbh_rom = (
        igdbh.get_rom_by_id(int(r_igbd_id_search))
        if r_igbd_id_search
        else igdbh.get_rom(rom_attrs["file_name"], platform.igdb_id)
    )

    rom_attrs.update(igdbh_rom)

    # Return early if not found in IGDB
    if not igdbh_rom["r_igdb_id"]:
        log.warning(
            f"\t   {r_igbd_id_search or rom_attrs['file_name']} not found in IGDB"
        )
        return Rom(**rom_attrs)

    log.info(emoji.emojize(f"\t   Identified as {igdbh_rom['r_name']} :alien_monster:"))

    # Update properties from IGDB
    rom_attrs.update(
        fs.get_cover(
            overwrite=overwrite,
            p_slug=platform.slug,
            r_name=rom_attrs["r_name"],
            url_cover=rom_attrs["url_cover"],
        )
    )
    rom_attrs.update(
        fs.get_screenshots(
            p_slug=platform.slug,
            r_name=rom_attrs["r_name"],
            url_screenshots=rom_attrs["url_screenshots"],
        )
    )

    return Rom(**rom_attrs)
