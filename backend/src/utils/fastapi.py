from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from handler import igdbh
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
    platform_attrs: dict = igdbh.get_platform_details(p_slug)
    platform_attrs['n_roms'] = fs.get_roms(p_slug, True, only_amount=True)
    platform = Platform(**platform_attrs)
    return platform


def scan_rom(platform: Platform, rom: dict, r_igbd_id_search: str = '', overwrite: bool = False) -> None:
    r_igdb_id, file_name_no_tags, r_slug, r_name, summary, url_cover = igdbh.get_rom_details(rom['file_name'], platform.igdb_id, r_igbd_id_search)
    path_cover_s, path_cover_l, has_cover = fs.get_cover_details(overwrite, platform.slug, rom['file_name'], url_cover)
    rom['file_name_no_tags'] = file_name_no_tags
    rom['r_igdb_id'] = r_igdb_id
    rom['p_igdb_id'] = platform.igdb_id
    rom['r_slug'] = r_slug
    rom['p_slug'] = platform.slug
    rom['name'] = r_name
    rom['summary'] = summary
    rom['path_cover_s'] = path_cover_s
    rom['path_cover_l'] = path_cover_l
    rom['has_cover'] = has_cover
    rom = Rom(**rom)
    return rom
