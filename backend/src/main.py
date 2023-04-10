import sys
import subprocess
from subprocess import CalledProcessError
from fastapi import FastAPI, Request
import uvicorn

from logger.logger import log
from handler import igdbh, dbh
from config import DEV_PORT, DEV_HOST
from models.platform import Platform
from utils import fs, fastapi


app = FastAPI()
fastapi.allow_cors(app)


@app.on_event("startup")
async def startup() -> None:
    """Startup application."""
    log.info("Applying migrations...")
    try:
        subprocess.run(['alembic', 'upgrade', 'head'], check=True)
    except CalledProcessError as e:
        log.critical(f"Could not apply migrations: {e}")
        sys.exit(4)


@app.put("/scan")
async def scan(req: Request, full_scan: bool=False, overwrite: bool=False) -> dict:
    """Scan platforms and roms and write them in database."""

    log.info("complete scaning...")
    fs.store_default_resources(overwrite)
    data: dict = await req.json()
    platforms: list[str] = data['platforms'] if data['platforms'] else fs.get_platforms()
    for p_slug in platforms:
        platform: Platform = fastapi.scan_platform(p_slug)
        roms: list[dict] = fs.get_roms(p_slug, full_scan)
        for rom in roms:
            fastapi.scan_rom(platform, rom)
        dbh.purge_roms(p_slug, fs.get_roms(p_slug, True))
    dbh.purge_platforms(fs.get_platforms())
    return {'msg': 'success'}


@app.get("/platforms")
async def platforms() -> dict:
    """Returns platforms data"""

    return {'data': dbh.get_platforms()}


@app.get("/platforms/{p_slug}/roms/{file_name}")
async def rom(p_slug: str, file_name: str) -> dict:
    """Returns one rom data of the desired platform"""

    return {'data':  dbh.get_rom(p_slug, file_name)}


@app.get("/platforms/{p_slug}/roms")
async def roms(p_slug: str) -> dict:
    """Returns all roms of the desired platform"""

    return {'data':  dbh.get_roms(p_slug)}


@app.patch("/platforms/{p_slug}/roms")
async def updateRom(req: Request, p_slug: str) -> dict:
    """Updates rom details"""

    data: dict = await req.json()
    rom: dict = data['rom']
    updatedRom: dict = data['updatedRom']
    r_igdb_id, file_name_no_tags, r_slug, r_name, summary, url_cover = igdbh.get_rom_details(updatedRom['file_name'], rom['p_igdb_id'], updatedRom['r_igdb_id'])
    path_cover_s, path_cover_l, has_cover = fs.get_cover_details(True, p_slug, updatedRom['file_name'], url_cover)
    updatedRom['file_name_no_tags'] = file_name_no_tags
    updatedRom['r_igdb_id'] = r_igdb_id
    updatedRom['p_igdb_id'] = rom['p_igdb_id']
    updatedRom['r_slug'] = r_slug
    updatedRom['p_slug'] = p_slug
    updatedRom['name'] = r_name
    updatedRom['summary'] = summary
    updatedRom['path_cover_s'] = path_cover_s
    updatedRom['path_cover_l'] = path_cover_l
    updatedRom['has_cover'] = has_cover
    updatedRom['file_path'] = rom['file_path']
    updatedRom['file_size'] = rom['file_size']
    updatedRom['file_extension'] = updatedRom['file_name'].split('.')[-1] if '.' in updatedRom['file_name'] else ""
    reg, rev, other_tags = fs.parse_tags(updatedRom['file_name'])
    updatedRom.update({'region': reg, 'revision': rev, 'tags': other_tags})
    if 'url_cover' in updatedRom.keys(): del updatedRom['url_cover']
    fs.rename_rom(p_slug, rom['file_name'], updatedRom['file_name'])
    dbh.update_rom(p_slug, rom['file_name'], updatedRom)
    return {'data': updatedRom}


@app.delete("/platforms/{p_slug}/roms/{file_name}")
async def delete_rom(p_slug: str, file_name: str, filesystem: bool=False) -> dict:
    """Detele rom from filesystem and database"""

    log.info("deleting rom...")
    if filesystem: fs.delete_rom(p_slug, file_name)
    dbh.delete_rom(p_slug, file_name)
    return {'msg': 'success'}


@app.put("/search/roms/igdb")
async def search_rom_igdb(req: Request) -> dict:
    """Get all the roms matched from igdb."""

    data: dict = await req.json()
    log.info(f"getting {data['rom']['file_name']} roms from {data['rom']['p_slug']} igdb ...")
    return {'data': igdbh.get_matched_roms(data['rom']['file_name'], data['rom']['p_igdb_id'], data['rom']['p_slug'])}


if __name__ == '__main__':
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
