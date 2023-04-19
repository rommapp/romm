from fastapi import APIRouter, Request

from logger.logger import log, COLORS
from handler import igdbh, dbh
from utils import fs

router = APIRouter()


@router.get("/platforms/{p_slug}/roms/{file_name}")
def rom(p_slug: str, file_name: str) -> dict:
    """Returns one rom data of the desired platform"""

    return {'data': dbh.get_rom(p_slug, file_name)}


@router.get("/platforms/{p_slug}/roms")
def roms(p_slug: str) -> dict:
    """Returns all roms of the desired platform"""

    return {'data':  dbh.get_roms(p_slug)}


@router.patch("/platforms/{p_slug}/roms")
async def updateRom(req: Request, p_slug: str) -> dict:
    """Updates rom details"""

    data: dict = await req.json()
    rom: dict = data['rom']
    updated_rom: dict = data['updatedRom']
    log.debug(updated_rom)
    log.info(f"Updating {COLORS['orange']}{updated_rom['file_name']}{COLORS['reset']} details")
    updated_rom.update(igdbh.get_rom_details(updated_rom['file_name'], rom['p_igdb_id'], updated_rom['r_igdb_id']))
    updated_rom.update(fs.get_cover_details(True, p_slug, updated_rom['file_name'], updated_rom['url_cover']))
    updated_rom['p_slug'] = p_slug
    updated_rom['p_igdb_id'] = rom['p_igdb_id']
    updated_rom['file_path'] = rom['file_path']
    updated_rom['file_size'] = rom['file_size']
    updated_rom['file_size_units'] = rom['file_size_units']
    updated_rom['multi'] = rom['multi']
    updated_rom['p_name'] = rom['p_name']
    updated_rom['file_extension'] = fs.get_file_extension(updated_rom)
    reg, rev, other_tags = fs.parse_tags(updated_rom['file_name'])
    updated_rom.update({'region': reg, 'revision': rev, 'tags': other_tags})
    fs.rename_rom(p_slug, rom['file_name'], updated_rom['file_name'])
    dbh.update_rom(p_slug, rom['file_name'], updated_rom)
    return {'data': updated_rom}


@router.delete("/platforms/{p_slug}/roms/{file_name}")
def remove_rom(p_slug: str, file_name: str, filesystem: bool=False) -> dict:
    """Detele rom from filesystem and database"""

    log.info(f"Deleting {file_name} from database")
    dbh.delete_rom(p_slug, file_name)
    if filesystem:
        log.info(f"Removing {file_name} from filesystem")
        fs.remove_rom(p_slug, file_name)
    return {'msg': 'success'}
