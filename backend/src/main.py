from dataclasses import asdict

from fastapi import FastAPI
import uvicorn

from logger.logger import log
from handler.igdb_handler import IGDBHandler
from handler.sgdb_handler import SGDBHandler
from handler.db_handler import DBHandler
from config.config import DEFAULT_IMAGE_URL
from data.data import Platform, Rom
from utils import fs, fastapi


app = FastAPI()
origins = fastapi.allow_cors(app)
igdbh: IGDBHandler = IGDBHandler()
dbh: DBHandler = DBHandler()


@app.get("/platforms")
async def platforms():
    """Returns platforms data"""
    return {'data': [Platform(*p) for p in dbh.get_platforms()]}


@app.get("/scan")
async def scan(overwrite: bool=False):
    """Scan platforms and roms and write them in database."""

    log.info("scaning...")

    fs.store_platform_logo('defaults', DEFAULT_IMAGE_URL)

    platforms: list = []

    for slug in fs.get_platforms():
        # Fetch platforms details from igdb
        igdb_id, name, url_logo = igdbh.get_platform_details(slug)
        sgdb_id: str = ""

        if (overwrite or not fs.platform_logo_exists(slug)) and url_logo:
            fs.store_platform_logo(slug, url_logo)

        details: list = [igdb_id, sgdb_id, slug, name]
        if fs.platform_logo_exists(slug):
            details.append(fs.get_platform_logo_path(slug))
      
        platforms.append(Platform(*details))

    # Create tables if not exists, truncate them if exists.
    dbh.create_platform_table(*asdict(Platform()).keys())
    # Write platforms in database
    dbh.write_platforms(platforms)

    return {'msg': 'success'}



if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True, workers=4)
    dbh.close_conn()
