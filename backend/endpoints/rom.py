from fastapi import APIRouter, Request, status, HTTPException

from logger.logger import log
from handler import dbh
from utils import fs, get_file_name_with_no_tags
from utils.exceptions import RomNotFoundError, RomAlreadyExistsException
from models.rom import Rom
from models.platform import Platform

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
    platform: Platform = dbh.get_platform(p_slug)
    try:
        fs.rename_rom(platform.fs_slug, db_rom.file_name, updated_rom['file_name'])
    except RomAlreadyExistsException as e:
        log.error(str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    updated_rom['file_name_no_tags'] = get_file_name_with_no_tags(updated_rom['file_name'])
    updated_rom.update(fs.get_cover(True, p_slug, updated_rom['file_name'], updated_rom['url_cover']))
    updated_rom.update(fs.get_screenshots(p_slug, updated_rom['file_name'], updated_rom['url_screenshots']))
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
            platform: Platform = dbh.get_platform(p_slug)
            fs.remove_rom(platform.fs_slug, rom.file_name)
        except RomNotFoundError as e:
            error = f"Couldn't delete from filesystem: {str(e)}"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
    return {'msg': f'{rom.file_name} deleted successfully!'}
