from fastapi import FastAPI, Request
import uvicorn

from logger.logger import log
from handler.igdb_handler import IGDBHandler
from handler.sgdb_handler import SGDBHandler
from handler.db_handler import DBHandler
from config.config import DEV_PORT, DEV_HOST
from utils import fs, fastapi


app = FastAPI()
fastapi.allow_cors(app)

igdbh: IGDBHandler = IGDBHandler()
sgdbh: SGDBHandler = SGDBHandler()
dbh: DBHandler = DBHandler()


@app.patch("/platforms/{p_slug}/roms/{filename}")
async def updateRom(req: Request, p_slug: str, filename: str):
    """Updates rom details"""

    data: dict = await req.json()
    if 'r_igdb_id' in data:
        r_igdb_id, filename_no_ext, r_slug, r_name, summary, url_cover = igdbh.get_rom_details(filename, data['p_igdb_id'], data['r_igdb_id'])
        path_cover_s, path_cover_l, has_cover = fs.get_cover_details(True, p_slug, filename_no_ext, url_cover)
        data['r_igdb_id'] = r_igdb_id
        data['filename_no_ext'] = filename_no_ext
        data['r_slug'] = r_slug
        data['name'] = r_name
        data['summary'] = summary
        data['path_cover_s'] = path_cover_s
        data['path_cover_l'] = path_cover_l
        data['has_cover'] = has_cover
        data['p_slug'] = p_slug
    else:
        fs.rename_rom(p_slug, filename, data)
        data['filename_no_ext'] = data['filename'].split('.')[0]
    dbh.update_rom(p_slug, filename, data)
    return {'data': data}


@app.delete("/platforms/{p_slug}/roms/{filename}")
async def delete_rom(p_slug: str, filename: str):
    """Detele rom from filesystem and database"""

    log.info("deleting rom...")
    fs.delete_rom(p_slug, filename)
    dbh.delete_rom(p_slug, filename)
    return {'msg': 'success'}


@app.get("/platforms/{p_slug}/roms/{filename}")
async def rom(p_slug: str, filename: str):
    """Returns one rom data of the desired platform"""

    return {'data':  dbh.get_rom(p_slug, filename)}


@app.get("/platforms/{p_slug}/roms")
async def roms(p_slug: str):
    """Returns all roms of the desired platform"""

    return {'data':  dbh.get_roms(p_slug)}


@app.get("/platforms")
async def platforms():
    """Returns platforms data"""

    return {'data': dbh.get_platforms()}


@app.put("/scan")
async def scan(req: Request, overwrite: bool=False):
    """Scan platforms and roms and write them in database."""

    log.info("complete scaning...")
    fs.store_default_resources(overwrite)
    data: dict = await req.json()
    platforms = data['platforms'] if data['platforms'] else fs.get_platforms()
    for p_slug in platforms:
        p_igdb_id: str = fastapi.scan_platform(overwrite, p_slug, igdbh, dbh)
        for rom in fs.get_roms(p_slug):
            fastapi.scan_rom(overwrite, rom, p_igdb_id, p_slug, igdbh, dbh)
        fastapi.purge(dbh, p_slug=p_slug)
    fastapi.purge(dbh)
    return {'msg': 'success'}


@app.put("/search/roms/igdb")
async def search_rom_igdb(req: Request):
    """Get all the roms matched from igdb."""

    data: dict = await req.json()
    log.info(f"getting {data['filename']} roms from {data['p_igdb_id']} igdb ...")
    return {'data': igdbh.get_matched_roms(data['filename'], data['p_igdb_id'])}


if __name__ == '__main__':
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
