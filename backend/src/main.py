from dataclasses import asdict

from fastapi import FastAPI
import uvicorn

from logger.logger import log
from handler.igdb_handler import IGDBHandler
from handler.sgdb_handler import SGDBHandler
from handler.db_handler import DBHandler
from config.config import PORT, HOST
from data.data import Platform, Rom
from utils import fs, fastapi


app = FastAPI()
fastapi.allow_cors(app)

igdbh: IGDBHandler = IGDBHandler()
sgdbh: SGDBHandler = SGDBHandler()
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

    platforms: list = []
    roms: list = []

    fs.store_default_resources(overwrite)

    for p_slug in fs.get_platforms():
        p_igdb_id, p_name, url_logo = igdbh.get_platform_details(p_slug)
        p_sgdb_id: str = ""

        details: list = [p_igdb_id, p_sgdb_id, p_slug, p_name]
        
        # TODO: refactor logo details logic
        if (overwrite or not fs.p_logo_exists(p_slug)) and url_logo:
            fs.store_p_logo(p_slug, url_logo)
        if fs.p_logo_exists(p_slug):
            details.append(fs.get_p_logo_path(p_slug))

        platforms.append(Platform(*details))

        for filename in fs.get_roms(p_slug):
            log.info(f"Getting {filename} details")
            r_igdb_id, filename_no_ext, r_slug, r_name, summary, url_cover = igdbh.get_rom_details(filename, p_igdb_id)
            r_sgdb_id: str = ""
            cover_path_s, cover_path_l, has_cover = fs.get_cover_details(overwrite, p_slug, filename_no_ext, url_cover)
            details: list = [r_igdb_id, r_sgdb_id, p_igdb_id, p_sgdb_id, 
                             filename_no_ext, filename, r_name, r_slug, summary, p_slug,
                             cover_path_s, cover_path_l, has_cover]
            roms.append(Rom(*details))

    dbh.regenerate_platform_table(*asdict(Platform()).keys())
    dbh.write_platforms(platforms)

    dbh.regenerate_rom_table(*asdict(Rom()).keys())
    dbh.write_roms(roms)

    return {'msg': 'success'}


if __name__ == '__main__':
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
    dbh.close_conn()
