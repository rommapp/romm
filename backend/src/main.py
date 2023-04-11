from fastapi import FastAPI, Request
import uvicorn
import json
import emoji

from logger.logger import log, COLORS
from handler import igdbh, dbh
from config import DEV_PORT, DEV_HOST
from models.platform import Platform
from utils import fs, fastapi


app = FastAPI()
fastapi.allow_cors(app)


@app.on_event("startup")
def startup() -> None:
    """Startup application."""
    pass


@app.get("/scan")
def scan(platforms_to_scan: str, full_scan: bool=False) -> dict:
    """Scan platforms and roms and write them in database."""

    log.info(emoji.emojize(":magnifying_glass_tilted_right: Scanning "))
    fs.store_default_resources()
    fs_platforms: list[str] = fs.get_platforms()
    platforms: list[str] = json.loads(platforms_to_scan) if len(json.loads(platforms_to_scan)) > 0 else fs_platforms
    log.info(f"Platforms detected: {', '.join(platforms)}")
    for p_slug in platforms:
        log.info(emoji.emojize(f":video_game: {p_slug} {COLORS['reset']}"))
        platform: Platform = fastapi.scan_platform(p_slug)
        if p_slug != str(platform): log.info(f"Identified as {COLORS['blue']}{platform}{COLORS['reset']}")
        dbh.add_platform(platform)
        log.info(f"Searching new roms")
        roms: list[dict] = fs.get_roms(p_slug, full_scan)
        for rom in roms:
            log.info(f"Getting {COLORS['orange']}{rom['file_name']}{COLORS['reset']} details")
            if rom['multi']: [log.info(f"\t - {COLORS['orange_i']}{file}{COLORS['reset']}") for file in rom['files']]
            rom = fastapi.scan_rom(platform, rom)
            dbh.add_rom(rom)    
    log.info(emoji.emojize(":wastebasket:  Purging database"))
    [dbh.purge_roms(p_slug, fs.get_roms(p_slug, True)) for p_slug in platforms]
    dbh.purge_platforms(fs_platforms)
    return {'msg': 'success'}


@app.get("/platforms")
def platforms() -> dict:
    """Returns platforms data"""

    return {'data': dbh.get_platforms()}


@app.get("/platforms/{p_slug}/roms/{file_name}")
def rom(p_slug: str, file_name: str) -> dict:
    """Returns one rom data of the desired platform"""

    return {'data':  dbh.get_rom(p_slug, file_name)}


@app.get("/platforms/{p_slug}/roms")
def roms(p_slug: str) -> dict:
    """Returns all roms of the desired platform"""

    return {'data':  dbh.get_roms(p_slug)}


@app.patch("/platforms/{p_slug}/roms")
async def updateRom(req: Request, p_slug: str) -> dict:
    """Updates rom details"""

    data: dict = await req.json()
    rom: dict = data['rom']
    updatedRom: dict = data['updatedRom']
    log.info(f"Updating {COLORS['orange']}{updatedRom['file_name']}{COLORS['reset']} details")
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
def remove_rom(p_slug: str, file_name: str, filesystem: bool=False) -> dict:
    """Detele rom from filesystem and database"""

    log.info(f"Deleting {file_name} from database")
    dbh.delete_rom(p_slug, file_name)
    if filesystem:
        log.info(f"Removing {file_name} from filesystem")
        fs.remove_rom(p_slug, file_name)
    return {'msg': 'success'}


@app.put("/search/roms/igdb")
async def search_rom_igdb(req: Request) -> dict:
    """Get all the roms matched from igdb."""

    data: dict = await req.json()
    log.info(emoji.emojize(":magnifying_glass_tilted_right: IGDB Searching"))
    log.info(emoji.emojize(f":video_game: {data['rom']['p_slug']}: {COLORS['orange']}{data['rom']['file_name']}{COLORS['reset']}"))
    matched_roms = igdbh.get_matched_roms(data['rom']['file_name'], data['rom']['p_igdb_id'], data['rom']['p_slug'])
    log.info("Results:")
    [log.info(f"\t - {COLORS['blue']}{rom['name']}{COLORS['reset']}") for rom in matched_roms]
    return {'data': matched_roms}


if __name__ == '__main__':
    uvicorn.run("main:app", host=DEV_HOST, port=DEV_PORT, reload=True)
