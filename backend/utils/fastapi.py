from handler import igdbh
from utils import fs, parse_tags, get_file_extension, get_file_name_with_no_tags
from config.config_loader import config
from models.platform import Platform
from models.rom import Rom


def scan_platform(fs_slug: str) -> Platform:
    """Get platform details

    Args:
        p_slug: short name of the platform
    Returns
        Platform object
    """

    platform_attrs = {}
    platform_attrs["fs_slug"] = fs_slug

    try:
        if fs_slug in config["PLATFORMS_BINDING"].keys():
            platform_attrs["slug"] = config["PLATFORMS_BINDING"][fs_slug]
        else:
            platform_attrs["slug"] = fs_slug
    except (KeyError, TypeError, AttributeError):
        platform_attrs["slug"] = fs_slug

    platform_attrs.update(igdbh.get_platform(platform_attrs["slug"]))
    platform_attrs["n_roms"] = len(fs.get_roms(platform_attrs["fs_slug"]))

    return Platform(**platform_attrs)


def scan_rom(
    platform: Platform,
    rom_attrs: dict,
    r_igbd_id_search: str = "",
    overwrite: bool = False,
) -> Rom:
    p_slug = platform.fs_slug if platform.fs_slug else platform.slug
    roms_path = fs.get_roms_structure(p_slug)

    if r_igbd_id_search:
        rom_attrs.update(igdbh.get_rom_by_id(r_igbd_id_search))
    else:
        rom_attrs.update(igdbh.get_rom(rom_attrs["file_name"], platform.igdb_id))

    rom_attrs.update(
        fs.get_cover(
            overwrite, platform.slug, rom_attrs["file_name"], rom_attrs["url_cover"]
        )
    )
    rom_attrs.update(
        fs.get_screenshots(
            platform.slug, rom_attrs["file_name"], rom_attrs["url_screenshots"]
        )
    )
    file_size, file_size_units = fs.get_rom_size(
        rom_attrs["multi"], rom_attrs["file_name"], rom_attrs["files"], roms_path
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

    return Rom(**rom_attrs)
