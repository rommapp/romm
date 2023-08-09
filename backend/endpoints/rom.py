import io
import tempfile
import zipfile
from fastapi import APIRouter, Request, status, HTTPException
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.cursor import CursorPage, CursorParams
from fastapi.responses import FileResponse
from pydantic import BaseModel

from logger.logger import log
from handler import dbh
from utils import fs, get_file_name_with_no_tags
from utils.exceptions import RomNotFoundError, RomAlreadyExistsException
from models.rom import Rom
from models.platform import Platform
from config import LIBRARY_BASE_PATH

router = APIRouter()


class RomSchema(BaseModel):
    id: int

    r_igdb_id: str
    p_igdb_id: str
    r_sgdb_id: str
    p_sgdb_id: str

    p_slug: str
    p_name: str

    file_name: str
    file_name_no_tags: str
    file_extension: str
    file_path: str
    file_size: float
    file_size_units: str

    r_name: str
    r_slug: str

    summary: str

    path_cover_s: str
    path_cover_l: str
    has_cover: bool
    url_cover: str

    region: str
    revision: str
    tags: list

    multi: bool
    files: list

    url_screenshots: list
    path_screenshots: list

    full_path: str
    download_path: str

    class Config(BaseModel.Config):
        orm_mode = True


@router.get("/platforms/{p_slug}/roms/{id}", status_code=200)
def rom(id: int) -> RomSchema:
    """Returns one rom data of the desired platform"""

    return dbh.get_rom(id)


@router.get("/platforms/{p_slug}/roms/{id}/download", status_code=200)
def download_rom(id: int, files: str):
    rom = dbh.get_rom(id)
    rom_path = f"{LIBRARY_BASE_PATH}/{rom.full_path}"

    if not rom.multi:
        return FileResponse(
            path=rom_path,
            filename=rom.file_name,
            media_type="application/octet-stream",
        )

    mf = io.BytesIO()
    with zipfile.ZipFile(mf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        try:
            for file_name in files.split(","):
                zf.write(f"{rom_path}/{file_name}", file_name)
        except FileNotFoundError as e:
            log.error(str(e))
        finally:
            zf.close()

    tmp = tempfile.NamedTemporaryFile(delete=False)
    with open(tmp.name, "wb") as f:
        f.write(mf.getvalue())

        return FileResponse(
            path=tmp.name,
            filename=f"{rom.r_name}.zip",
            media_type="application/octet-stream",
        )


@router.get("/platforms/{p_slug}/roms", status_code=200)
def roms(
    p_slug: str, size: int = 60, cursor: str = "", search_term: str = ""
) -> CursorPage[RomSchema]:
    """Returns all roms of the desired platform"""
    with dbh.session.begin() as session:
        cursor_params = CursorParams(size=size, cursor=cursor)
        qq = dbh.get_roms(p_slug)

        if search_term:
            return paginate(
                session,
                qq.filter(Rom.file_name.ilike(f"%{search_term}%")),
                cursor_params,
            )

        return paginate(session, qq, cursor_params)  # type: ignore


@router.patch("/platforms/{p_slug}/roms/{id}", status_code=200)
async def updateRom(req: Request, p_slug: str, id: int) -> dict:
    """Updates rom details"""

    data: dict = await req.json()
    updated_rom: dict = data["updatedRom"]
    db_rom: Rom = dbh.get_rom(id)
    platform: Platform = dbh.get_platform(p_slug)

    file_name = updated_rom.get("file_name", db_rom.file_name)

    try:
        if file_name != db_rom.file_name:  # type: ignore
            fs.rename_rom(platform.fs_slug, db_rom.file_name, file_name)  # type: ignore
    except RomAlreadyExistsException as e:
        log.error(str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    updated_rom["file_name_no_tags"] = get_file_name_with_no_tags(file_name)  # type: ignore
    updated_rom.update(fs.get_cover(overwrite=True, p_slug=p_slug, r_name=updated_rom["file_name_no_tags"], url_cover=updated_rom["url_cover"]))  # type: ignore
    updated_rom.update(
        fs.get_screenshots(p_slug=p_slug, r_name=updated_rom["file_name_no_tags"], url_screenshots=updated_rom["url_screenshots"]),  # type: ignore
    )
    dbh.update_rom(id, updated_rom)

    return {
        "rom": dbh.get_rom(id),
        "msg": f"{file_name} updated successfully!",
    }


@router.delete("/platforms/{p_slug}/roms/{id}", status_code=200)
def delete_rom(p_slug: str, id: int, filesystem: bool = False) -> dict:
    """Detele rom from database [and filesystem]"""

    rom: Rom = dbh.get_rom(id)
    log.info(f"Deleting {rom.file_name} from database")
    dbh.delete_rom(id)
    dbh.update_n_roms(p_slug)

    if filesystem:
        log.info(f"Deleting {rom.file_name} from filesystem")
        try:
            platform: Platform = dbh.get_platform(p_slug)
            fs.remove_rom(platform.fs_slug, rom.file_name)  # type: ignore
        except RomNotFoundError as e:
            error = f"Couldn't delete from filesystem: {str(e)}"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return {"msg": f"{rom.file_name} deleted successfully!"}
