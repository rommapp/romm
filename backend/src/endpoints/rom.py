from fastapi import APIRouter, Request, status, HTTPException

from logger.logger import log
from handler import dbh
from utils import fs
from utils.exceptions import RomNotFoundError, RomAlreadyExistsException
from models.rom import Rom

router = APIRouter()


@router.get("/platforms/{p_slug}/roms/{id}", status_code=200)
def rom(id: int) -> dict:
    """Returns one rom data of the desired platform"""

    return {'data': dbh.get_rom(id)}


@router.get("/platforms/{p_slug}/roms", status_code=200)
def roms(p_slug: str) -> dict:
    """Returns all roms of the desired platform"""

    return {'data':  dbh.get_roms(p_slug)}


@router.patch("/platforms/{p_slug}/roms/{id}", status_code=200)
async def updateRom(req: Request, p_slug: str, id: int) -> dict:
    """Updates rom details"""

    data: dict = await req.json()
    updated_rom: dict = data['updatedRom']
    db_rom: Rom = dbh.get_rom(id)
    try:
        fs.rename_rom(p_slug, db_rom.file_name, updated_rom['file_name'])
    except RomAlreadyExistsException as e:
        error: str = f"{e}"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error)
    updated_rom.update(fs.get_cover_details(True, p_slug, updated_rom['file_name'], updated_rom['url_cover']))
    dbh.update_rom(id, updated_rom)
    return {'data': dbh.get_rom(id), 'msg': f"{updated_rom['file_name']} updated successfully!"}


@router.delete("/platforms/{p_slug}/roms/{id}", status_code=200)
def delete_rom(p_slug: str, id: int, filesystem: bool=False) -> dict:
    """Detele rom from database [and filesystem]"""

    rom: Rom = dbh.get_rom(id)
    log.info(f"Deleting {rom.file_name} from database")
    dbh.delete_rom(id)
    if filesystem:
        log.info(f"Deleting {rom.file_name} from filesystem")
        try:
            fs.remove_rom(p_slug, rom.file_name)
        except RomNotFoundError as e:
            error: str = f"{e}. Couldn't delete from filesystem."
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
    return {'msg': f'{rom.file_name} deleted successfully!'}
