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


@app.get("/platforms/{p_slug}/roms")
async def roms(p_slug: str):
    """Returns roms data of the desired platform"""
    return {'data':  dbh.get_roms(p_slug)}


@app.patch("/platforms/{p_slug}/roms/{filename}")
async def updateRom(req: Request, p_slug: str, filename: str):
    """Updates rom details"""
    data: dict = await req.json()
    if 'filename' in data: fs.rename_rom(p_slug, filename, data)
    dbh.update_rom(p_slug, filename, data)
    dbh.commit()
    return {'msg': 'success'}


@app.delete("/platforms/{p_slug}/roms/{filename}")
async def delete_rom(p_slug: str, filename: str):
    log.info("deleting rom...")
    fs.delete_rom(p_slug, filename)
    dbh.delete_rom(p_slug, filename)
    dbh.commit()
    return {'msg': 'success'}


@app.get("/platforms")
async def platforms():
    """Returns platforms data"""
    return {'data': dbh.get_platforms()}


@app.get("/scan/rom")
async def scan_rom(req: Request, overwrite: bool=False):
    """Scan single rom and write it in database."""

    log.info("scaning rom...")
    data: dict = await req.json()
    fastapi.scan_rom(overwrite, data['filename'], data['p_igdb_id'], data['p_slug'], igdbh, dbh)
    dbh.commit()
    return {'msg': 'success'}


@app.get("/scan/platform")
async def scan_platform(req: Request, overwrite: bool=False):
    """Scan single platform and write it in database."""

    log.info("scaning platform roms...")
    data: dict = await req.json()
    for filename in fs.get_roms(data['p_slug']):
        fastapi.scan_rom(overwrite, filename, data['p_igdb_id'], data['p_slug'], igdbh, dbh)
    dbh.commit()
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
    dbh.commit()
    return {'msg': 'success'}


if __name__ == '__main__':
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
