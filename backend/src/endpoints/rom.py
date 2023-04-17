from fastapi import APIRouter, Request

from logger.logger import log, COLORS
from handler import igdbh, dbh
from utils import fs

router = APIRouter()


@router.get("/platforms/{p_slug}/roms/{file_name}")
def rom(p_slug: str, file_name: str) -> dict:
    """Returns one rom data of the desired platform"""

    return {'data':  dbh.get_rom(p_slug, file_name)}


@router.get("/platforms/{p_slug}/roms")
def roms(p_slug: str) -> dict:
    """Returns all roms of the desired platform"""

    return {'data':  dbh.get_roms(p_slug)}


@router.patch("/platforms/{p_slug}/roms")
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
    updatedRom['multi'] = rom['multi']
    updatedRom['file_extension'] = fs.get_file_extension(updatedRom)
    reg, rev, other_tags = fs.parse_tags(updatedRom['file_name'])
    updatedRom.update({'region': reg, 'revision': rev, 'tags': other_tags})
    if 'url_cover' in updatedRom.keys(): del updatedRom['url_cover']
    fs.rename_rom(p_slug, rom['file_name'], updatedRom['file_name'])
    dbh.update_rom(p_slug, rom['file_name'], updatedRom)
    return {'data': updatedRom}


@router.delete("/platforms/{p_slug}/roms/{file_name}")
def remove_rom(p_slug: str, file_name: str, filesystem: bool=False) -> dict:
    """Detele rom from filesystem and database"""

    log.info(f"Deleting {file_name} from database")
    dbh.delete_rom(p_slug, file_name)
    if filesystem:
        log.info(f"Removing {file_name} from filesystem")
        fs.remove_rom(p_slug, file_name)
    return {'msg': 'success'}
