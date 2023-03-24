from fastapi import FastAPI, Request
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
async def updateRom(req: Request, p_slug: str, filename: str):
    """Updates rom details"""

    data: dict = await req.json()
    if 'filename' in data: fs.rename_rom(p_slug, filename, data)
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
async def roms(p_slug: str, filename: str):
    """Returns rom data of the desired platform"""

    return {'data':  dbh.get_rom(p_slug, filename)}


@app.get("/platforms/{p_slug}/roms")
async def roms(p_slug: str):
    """Returns roms data of the desired platform"""

    return {'data':  dbh.get_roms(p_slug)}


@app.get("/platforms")
async def platforms():
    """Returns platforms data"""

    return {'data': dbh.get_platforms()}


@app.put("/scan/rom")
async def scan_rom(req: Request, overwrite: bool=False):
    """Scan single rom and write it in database."""

    data: dict = await req.json()
    log.info(f"scaning {data['filename']} rom...")
    fastapi.scan_rom(overwrite, data['filename'], data['p_igdb_id'], data['p_slug'], igdbh, dbh)
    return {'msg': 'success'}


@app.put("/scan/platform")
async def scan_platform(req: Request, overwrite: bool=False):
    """Scan single platform and write it in database."""

    data: dict = await req.json()
    log.info(f"scaning {data['p_slug']} roms...")
    for filename in fs.get_roms(data['p_slug']):
        fastapi.scan_rom(overwrite, filename, data['p_igdb_id'], data['p_slug'], igdbh, dbh)
    fastapi.purge(dbh, p_slug=data['p_slug'])
    return {'msg': 'success'}


@app.get("/scan")
async def scan(overwrite: bool=False):
    """Scan platforms and roms and write them in database."""

    log.info("complete scaning...")
    fs.store_default_resources(overwrite)
    for p_slug in fs.get_platforms():
        p_igdb_id: str = fastapi.scan_platform(overwrite, p_slug, igdbh, dbh)
        for filename in fs.get_roms(p_slug):
            fastapi.scan_rom(overwrite, filename, p_igdb_id, p_slug, igdbh, dbh)
    fastapi.purge(dbh)
    return {'msg': 'success'}


@app.put("/search/roms/igdb")
async def rom_igdb(req: Request):
    """Get all the roms matched from igdb."""

    data: dict = await req.json()
    log.info(f"getting {data['filename']} roms from {data['p_igdb_id']} igdb ...")
    return {'data': igdbh.get_matched_roms(data['filename'], data['p_igdb_id'])}


if __name__ == '__main__':
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
