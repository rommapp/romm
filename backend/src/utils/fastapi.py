from logger.logger import log
from handler import igdbh
from utils import parse_tags, get_file_extension
from utils import fs
from models.platform import Platform
from models.rom import Rom


def scan_platform(p_slug: str) -> Platform:
    """Get platform details

    Args:
        p_slug: short name of the platform
    Returns
        Platform object
    """
    platform_attrs: dict = igdbh.get_platform_details(p_slug)
    platform_attrs['n_roms'] = len(fs.get_roms(p_slug))
    platform = Platform(**platform_attrs)
    return platform


def scan_rom(platform: Platform, rom_attrs: dict, r_igbd_id_search: str = '', overwrite: bool = False) -> Rom:
    roms_path: str = fs.get_roms_structure(platform.slug)
    rom_attrs.update(igdbh.get_rom_details(rom_attrs['file_name'], platform.igdb_id, r_igbd_id_search))
    rom_attrs.update(fs.get_cover_details(overwrite, platform.slug, rom_attrs['file_name'], rom_attrs['url_cover']))
    file_size, file_size_units = fs.get_file_size(rom_attrs['multi'], rom_attrs['file_name'], rom_attrs['files'], roms_path)
    reg, rev, other_tags = parse_tags(rom_attrs['file_name'])
    rom_attrs.update({'file_path': roms_path, 'file_name': rom_attrs['file_name'], 'file_extension': get_file_extension(rom_attrs),
                      'multi': rom_attrs['multi'], 'file_size': file_size, 'file_size_units': file_size_units,
                      'region': reg, 'revision': rev, 'tags': other_tags})
    rom_attrs['p_igdb_id'] = platform.igdb_id
    rom_attrs['p_slug'] = platform.slug
    rom_attrs['p_name'] = platform.name
    rom = Rom(**rom_attrs)
    return rom
