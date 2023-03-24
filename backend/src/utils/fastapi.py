from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils import fs
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


def scan_platform(overwrite: bool, p_slug: str, igdbh, dbh) -> str:
    platform: dict  = {}
    log.info(f"Getting {p_slug} details")
    p_igdb_id, p_name, url_logo = igdbh.get_platform_details(p_slug)
    platform['slug'] = p_slug
    platform['igdb_id'] = p_igdb_id
    platform['name'] = p_name
    #TODO: refactor logo details logic
    if (overwrite or not fs.p_logo_exists(p_slug)) and url_logo:
        fs.store_p_logo(p_slug, url_logo)
    if fs.p_logo_exists(p_slug):
        platform['path_logo']: str = fs.get_p_path_logo(p_slug)
    dbh.add_platform(**platform)
    return p_igdb_id


def scan_rom(overwrite: bool, filename: str, p_igdb_id: str, p_slug: str, igdbh, dbh, r_igbd_id: str = '') -> None:
    rom: dict = {}
    log.info(f"Getting {filename} details")
    r_igdb_id, filename_no_ext, r_slug, r_name, summary, url_cover = igdbh.get_rom_details(filename, p_igdb_id, r_igbd_id)
    path_cover_s, path_cover_l, has_cover = fs.get_cover_details(overwrite, p_slug, filename_no_ext, url_cover)
    rom['filename'] = filename
    rom['filename_no_ext'] = filename_no_ext
    rom['r_igdb_id'] = r_igdb_id
    rom['p_igdb_id'] = p_igdb_id
    rom['name'] = r_name
    rom['r_slug'] = r_slug
    rom['p_slug'] = p_slug
    rom['summary'] = summary
    rom['path_cover_s'] = path_cover_s
    rom['path_cover_l'] = path_cover_l
    rom['has_cover'] = has_cover
    dbh.add_rom(**rom)


def purge(dbh, p_slug: str = None) -> None:
    """Clean the database from non existent platforms or roms"""
    if p_slug:
        # Purge only roms in platform
        roms: list = fs.get_roms(p_slug)
        dbh.purge_roms(p_slug, roms)
    else:
        # Purge all platforms / delete non existent platforms and non existen roms
        platforms: list = fs.get_platforms()
        dbh.purge_platforms(platforms)
        for p_slug in platforms:
            roms: list = fs.get_roms(p_slug)
            dbh.purge_roms(p_slug, roms)
