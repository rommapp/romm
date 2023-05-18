import emoji
from fastapi import APIRouter, Request, status, HTTPException

from logger.logger import log
from handler import dbh
from utils import fs, get_file_name_with_no_tags
from utils.exceptions import RomNotFoundError, RomAlreadyExistsException
from models.platform import Platform

router = APIRouter()


@router.get("/platforms/{p_slug}/roms/{id}", status_code=200)
def rom(id: int) -> dict:
    """Returns one rom data of the desired platform"""

    return {"data": dbh.get_rom(id)}


@router.get("/platforms/{p_slug}/roms", status_code=200)
def roms(p_slug: str) -> dict:
    """Returns all roms of the given platform"""

    return {"data": dbh.get_roms(p_slug)}


async def rename_all_roms(_sid: str, platform_slug: str, sm=None) -> dict:
    """Renames all ROMs of the given platform to IGDB format"""

    platform = dbh.get_platform(platform_slug)
    platform_roms = [r for r in dbh.get_roms(platform_slug) if r.r_igdb_id]
    log.info(emoji.emojize(f":pencil: Renaming all {platform.name} ROMs"))

    for rom in platform_roms:
        try:
            ext = rom.file_name.split(".")[-1]
            new_filename = rom.r_name
            if rom.region:
                new_filename += f" [{rom.region}]"
            if rom.revision:
                new_filename += f" [Rev {rom.revision}]"
            new_filename += f".{ext}"

            fs.rename_rom(platform.fs_slug, rom.file_name, new_filename)
            dbh.update_rom(
                rom.id,
                {
                    "file_name": new_filename,
                    "file_name_no_tags": get_file_name_with_no_tags(new_filename),
                },
            )
            log.info(f"Renamed {rom.file_name} to {new_filename}")
        except RomAlreadyExistsException as e:
            log.warning(str(e))

    await sm.emit("mass_rename:done")


@router.patch("/platforms/{p_slug}/roms/{id}", status_code=200)
async def updateRom(req: Request, p_slug: str, id: int) -> dict:
    """Updates rom details"""

    data = await req.json()
    updated_rom: dict = data["updatedRom"]
    db_rom = dbh.get_rom(id)
    platform = dbh.get_platform(p_slug)

    try:
        fs.rename_rom(platform.fs_slug, db_rom.file_name, updated_rom["file_name"])
    except RomAlreadyExistsException as e:
        log.error(str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    updated_rom["file_name_no_tags"] = get_file_name_with_no_tags(
        updated_rom["file_name"]
    )
    updated_rom.update(
        fs.get_cover(True, p_slug, updated_rom["file_name"], updated_rom["url_cover"])
    )
    updated_rom.update(
        fs.get_screenshots(
            p_slug, updated_rom["file_name"], updated_rom["url_screenshots"]
        )
    )
    dbh.update_rom(id, updated_rom)

    return {
        "data": dbh.get_rom(id),
        "msg": f"{updated_rom['file_name']} updated successfully!",
    }


@router.delete("/platforms/{p_slug}/roms/{id}", status_code=200)
def delete_rom(p_slug: str, id: int, filesystem: bool = False) -> dict:
    """Detele rom from database [and filesystem]"""

    rom = dbh.get_rom(id)
    log.info(f"Deleting {rom.file_name} from database")
    dbh.delete_rom(id)

    if filesystem:
        log.info(f"Deleting {rom.file_name} from filesystem")
        try:
            platform: Platform = dbh.get_platform(p_slug)
            fs.remove_rom(platform.fs_slug, rom.file_name)
        except RomNotFoundError as e:
            error = f"{str(e)}. Couldn't delete from filesystem."
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return {"msg": f"{rom.file_name} deleted successfully!"}
