from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from handler import igdbh, dbh
from utils import fs
from models.platform import Platform
from models.rom import Rom
from logger.logger import log


def allow_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    log.info("CORS enabled")


def scan_platform(p_slug: str) -> Platform:
    """Get platform details from IGDB if possible

    Args:
        p_slug: short name of the platform
    Returns
        Platform object
    """
    log.info(f"Getting {p_slug} details")
    platform_attrs: dict = igdbh.get_platform_details(p_slug)
    platform_attrs['slug'] = p_slug
    platform_attrs['path_logo'] = ''
    platform_attrs['n_roms'] = fs.get_roms(p_slug, only_amount=True)
    log.info(f"Platform n_roms: {platform_attrs['n_roms']}")
    platform = Platform(**platform_attrs)
    dbh.add_platform(platform)
    return platform


def scan_rom(platform: Platform, rom: dict, r_igbd_id_search: str = '', overwrite: bool = False) -> None:
    log.info(f"Getting {rom['filename']} details")
    r_igdb_id, filename_no_ext, r_slug, r_name, summary, url_cover = igdbh.get_rom_details(rom['filename'], platform.igdb_id, r_igbd_id_search)
    path_cover_s, path_cover_l, has_cover = fs.get_cover_details(overwrite, platform.slug, filename_no_ext, url_cover)
    rom_attrs: dict = {
        'filename': rom['filename'],
        'filename_no_ext': filename_no_ext,
        'size': rom['size'],
        'r_igdb_id': r_igdb_id,
        'p_igdb_id': platform.igdb_id,
        'name': r_name,
        'r_slug': r_slug,
        'p_slug': platform.slug,
        'summary': summary,
        'path_cover_s': path_cover_s,
        'path_cover_l': path_cover_l,
        'has_cover': has_cover
    }
    rom = Rom(**rom_attrs)
    dbh.add_rom(rom)
