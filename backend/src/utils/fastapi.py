from handler import igdbh
from utils import fs
from models.platform import Platform
from models.rom import Rom


def scan_platform(p_slug: str) -> Platform:
    """Get platform details from IGDB if possible

    Args:
        p_slug: short name of the platform
    Returns
        Platform object
    """
    platform_attrs: dict = igdbh.get_platform_details(p_slug)
    platform_attrs['n_roms'] = fs.get_roms(p_slug, True, only_amount=True)
    platform = Platform(**platform_attrs)
    return platform


def scan_rom(platform: Platform, rom: dict, r_igbd_id_search: str = '', overwrite: bool = False) -> None:
    rom.update(igdbh.get_rom_details(rom['file_name'], platform.igdb_id, r_igbd_id_search))
    rom.update(fs.get_cover_details(overwrite, platform.slug, rom['file_name'], rom['url_cover']))
    rom['p_igdb_id'] = platform.igdb_id
    rom['p_slug'] = platform.slug
    rom['p_name'] = platform.name
    rom = Rom(**rom)
    return rom
