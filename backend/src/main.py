from fastapi import FastAPI
import uvicorn

from logger.logger import log
from handler.igdb_handler import IGDBHandler
from handler.sgdb_handler import SGDBHandler
from handler.db_handler import DBHandler
from config.config import PORT, HOST
from utils import fs, fastapi


app = FastAPI()
fastapi.allow_cors(app)

igdbh: IGDBHandler = IGDBHandler()
sgdbh: SGDBHandler = SGDBHandler()
dbh: DBHandler = DBHandler()


@app.patch("/platforms/{p_slug}/roms/{filename}")
async def editRom(p_slug: str, filename: str):
    """Edits rom details"""
    return {'msg': 'WIP'}


@app.get("/platforms/{p_slug}/roms")
async def platforms(p_slug: str):
    """Returns roms data of the desired platform"""
    return {'data':  dbh.get_roms(p_slug)}


@app.get("/platforms")
async def platforms():
    """Returns platforms data"""
    return {'data': dbh.get_platforms()}


@app.get("/scan")
async def scan(overwrite: bool=False):
    """Scan platforms and roms and write them in database."""

    log.info("scaning...")

    fs.store_default_resources(overwrite)

    for p_slug in fs.get_platforms():
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

        for filename in fs.get_roms(p_slug):
            rom: dict = {}
            log.info(f"Getting {filename} details")
            r_igdb_id, filename_no_ext, r_slug, r_name, summary, url_cover = igdbh.get_rom_details(filename, p_igdb_id)
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
    
    dbh.commit()

    return {'msg': 'success'}


if __name__ == '__main__':
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
