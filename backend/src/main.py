from dataclasses import asdict

from fastapi import FastAPI
import uvicorn

from logger.logger import log
from handler.igdb_handler import IGDBHandler
from handler.sgdb_handler import SGDBHandler
from handler.db_handler import DBHandler
from config.config import PORT, HOST, DEFAULT_LOGO_URL, DEFAULT_COVER_URL_BIG, DEFAULT_COVER_URL_SMALL
from data.data import Platform, Rom
from utils import fs, fastapi


app = FastAPI()
fastapi.allow_cors(app)

igdbh: IGDBHandler = IGDBHandler()
dbh: DBHandler = DBHandler()


@app.get("/platforms/{slug}/roms")
async def platforms(slug):
    """Returns roms data of the desired platform"""
    return {'data': [Rom(*r) for r in dbh.get_roms(slug)]}


@app.get("/platforms")
async def platforms():
    """Returns platforms data"""
    return {'data': [Platform(*p) for p in dbh.get_platforms()]}


@app.get("/scan")
async def scan(overwrite: bool=False):
    """Scan platforms and roms and write them in database."""

    log.info("scaning...")

    if overwrite or not fs.platform_logo_exists('default'):
        fs.store_platform_logo('default', DEFAULT_LOGO_URL)
    if overwrite or not fs.rom_cover_exists('default', 'cover', 'big'):
        fs.store_rom_cover('default', 'cover', DEFAULT_COVER_URL_BIG, 'big')
    if overwrite or not fs.rom_cover_exists('default', 'cover', 'small'):
        fs.store_rom_cover('default', 'cover', DEFAULT_COVER_URL_SMALL, 'small')

    platforms: list = []
    roms: list = []

    for platform_slug in fs.get_platforms():
        platform_igdb_id, platform_name, url_logo = igdbh.get_platform_details(platform_slug)
        platform_sgdb_id: str = ""
        if not platform_name: platform_name = platform_slug
        details: list = [platform_igdb_id, platform_sgdb_id, platform_slug, platform_name]
        if (overwrite or not fs.platform_logo_exists(platform_slug)) and url_logo:
            fs.store_platform_logo(platform_slug, url_logo)
        if fs.platform_logo_exists(platform_slug):
            details.append(fs.get_platform_logo_path(platform_slug))
        platforms.append(Platform(*details))

        for rom_filename in fs.get_roms(platform_slug):
            log.info(f"Getting {rom_filename} details")
            rom_igdb_id, rom_filename_no_ext, rom_slug, rom_name, summary, url_cover = igdbh.get_rom_details(rom_filename, platform_igdb_id)
            rom_sgdb_id: str = ""
            if not rom_name: rom_name = rom_filename
            details: list = [rom_igdb_id, rom_sgdb_id, platform_igdb_id, platform_sgdb_id, rom_filename_no_ext, rom_filename, rom_name, rom_slug, summary, platform_slug]

            if (overwrite or not fs.rom_cover_exists(platform_slug, rom_filename, 'big')) and url_cover:
                fs.store_rom_cover(platform_slug, rom_filename, url_cover, 'big')

            if (overwrite or not fs.rom_cover_exists(platform_slug, rom_filename, 'small')) and url_cover:                
                fs.store_rom_cover(platform_slug, rom_filename, url_cover, 'small')

            if fs.rom_cover_exists(platform_slug, rom_filename, 'big'):
                details.append(fs.get_rom_cover_path(platform_slug, rom_filename, 'big'))

            if fs.rom_cover_exists(platform_slug, rom_filename, 'small'):
                details.append(fs.get_rom_cover_path(platform_slug, rom_filename, 'small'))

            roms.append(Rom(*details))

    dbh.regenerate_platform_table(*asdict(Platform()).keys())
    dbh.write_platforms(platforms)

    dbh.regenerate_rom_table(*asdict(Rom()).keys())
    dbh.write_roms(roms)

    return {'msg': 'success'}


if __name__ == '__main__':
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True, workers=4)
    dbh.close_conn()
