from fastapi import APIRouter, Request

from logger.logger import log
from handler import dbh
from utils import fs
from models.rom import Rom

router = APIRouter()


@router.get("/platforms/{p_slug}/roms/{id}")
def rom(id: int) -> dict:
    """Returns one rom data of the desired platform"""

    return {'data': dbh.get_rom(id)}


@router.get("/platforms/{p_slug}/roms")
def roms(p_slug: str) -> dict:
    """Returns all roms of the desired platform"""

    return {'data':  dbh.get_roms(p_slug)}


@router.patch("/platforms/{p_slug}/roms/{id}")
async def updateRom(req: Request, p_slug: str, id: int) -> dict:
    """Updates rom details"""

    data: dict = await req.json()
    updated_rom: dict = data['updatedRom']
    updated_rom.update(fs.get_cover_details(True, p_slug, updated_rom['file_name'], updated_rom['url_cover']))
    db_rom: Rom = dbh.get_rom(id)
    dbh.update_rom(id, updated_rom)
    fs.rename_rom(p_slug, db_rom.file_name, updated_rom['file_name'])
    return {'data': dbh.get_rom(id)}


@router.delete("/platforms/{p_slug}/roms/{id}")
def remove_rom(id: int, filesystem: bool=False) -> dict:
    """Detele rom from filesystem and database"""

    log.info(f"Deleting {id} from database")
    dbh.delete_rom(id)
    if filesystem:
        log.info(f"Removing {id} from filesystem")
        #TODO: remove from fs
        # fs.remove_rom(p_slug, file_name)
    return {'msg': 'success'}
