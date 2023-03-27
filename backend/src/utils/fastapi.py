from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from handler.db_handler import DBHandler
from handler.igdb_handler import IGDBHandler
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


def scan_platform(overwrite: bool, p_slug: str, igdbh: IGDBHandler, dbh: DBHandler) -> str:
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
        platform['path_logo'] = fs.get_p_path_logo(p_slug)
    platform['n_roms'] = len(fs.get_roms(p_slug))
    dbh.add_platform(**platform)
    return p_igdb_id


def scan_rom(overwrite: bool, rom, p_igdb_id: str, p_slug: str, igdbh: IGDBHandler, dbh: DBHandler, r_igbd_id: str = '') -> None:
    log.info(f"Getting {rom['filename']} details")
    r_igdb_id, filename_no_ext, r_slug, r_name, summary, url_cover = igdbh.get_rom_details(rom['filename'], p_igdb_id, r_igbd_id)
    path_cover_s, path_cover_l, has_cover = fs.get_cover_details(overwrite, p_slug, filename_no_ext, url_cover)
    rom: dict = {
        'filename': rom['filename'], 'filename_no_ext': filename_no_ext, 'size': rom['size'],
        'r_igdb_id': r_igdb_id, 'p_igdb_id': p_igdb_id,
        'name': r_name, 'r_slug': r_slug, 'p_slug': p_slug,
        'summary': summary,
        'path_cover_s': path_cover_s, 'path_cover_l': path_cover_l, 'has_cover': has_cover
    }
    dbh.add_rom(**rom)


def purge(dbh: DBHandler, p_slug: str = '') -> None:
    """Clean the database from non existent platforms or roms"""
    if p_slug:
        # Purge only roms in platform
        dbh.purge_roms(p_slug, fs.get_roms(p_slug))
    else:
        # Purge all platforms / delete non existent platforms and non existen roms
        platforms: list = fs.get_platforms()
        dbh.purge_platforms(platforms)
        for p_slug in platforms:
            dbh.purge_roms(p_slug, fs.get_roms(p_slug))
