from datetime import datetime
import json
from typing import Optional, Annotated
from typing_extensions import TypedDict
from fastapi import (
    APIRouter,
    Request,
    status,
    HTTPException,
    File,
    UploadFile,
)
from fastapi import Query
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.cursor import CursorPage, CursorParams
from fastapi.responses import FileResponse
from pydantic import BaseModel

from stat import S_IFREG
from stream_zip import ZIP_64, stream_zip  # type: ignore[import]

from config import LIBRARY_BASE_PATH
from logger.logger import log
from models import Rom
from handler import dbh
from endpoints.assets import SaveSchema, StateSchema, ScreenshotSchema
from exceptions.fs_exceptions import RomAlreadyExistsException
from utils.oauth import protected_route
from utils import get_file_name_with_no_tags
from utils.fs import (
    _file_exists,
    build_artwork_path,
    build_upload_file_path,
    rename_file,
    get_rom_cover,
    get_rom_screenshots,
    remove_file,
    get_fs_structure,
)

from .utils import CustomStreamingResponse

router = APIRouter()


class RomSchema(BaseModel):
    id: int
    igdb_id: Optional[int]
    sgdb_id: Optional[int]

    platform_slug: str
    platform_name: str

    file_name: str
    file_name_no_tags: str
    file_extension: str
    file_path: str
    file_size: float
    file_size_units: str
    file_size_bytes: int

    name: Optional[str]
    slug: Optional[str]
    summary: Optional[str]
    sort_comparator: str

    path_cover_s: str
    path_cover_l: str
    has_cover: bool
    url_cover: str

    revision: Optional[str]
    regions: list[str]
    languages: list[str]
    tags: list[str]
    multi: bool
    files: list[str]
    saves: list[SaveSchema]
    states: list[StateSchema]
    screenshots: list[ScreenshotSchema]
    merged_screenshots: list[str]
    full_path: str
    download_path: str

    class Config:
        from_attributes = True


class EnhancedRomSchema(RomSchema):
    sibling_roms: list["RomSchema"]


@protected_route(router.get, "/roms/{id}", ["roms.read"])
def rom(request: Request, id: int) -> EnhancedRomSchema:
    """Returns one rom data of the desired platform"""
    return dbh.get_rom(id)


@protected_route(router.get, "/roms-recent", ["roms.read"])
def recent_roms(request: Request) -> list[RomSchema]:
    """Returns the last 15 added roms"""
    return dbh.get_recent_roms()


class UploadRomResponse(TypedDict):
    uploaded_roms: list[str]
    skipped_roms: list[str]


@protected_route(router.put, "/roms/upload", ["roms.write"])
def upload_roms(
    request: Request, platform_slug: str, roms: list[UploadFile] = File(...)
) -> UploadRomResponse:
    platform_fs_slug = dbh.get_platform(platform_slug).fs_slug
    log.info(f"Uploading roms to {platform_fs_slug}")
    if roms is None:
        log.error("No roms were uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No roms were uploaded",
        )

    roms_path = build_upload_file_path(platform_fs_slug)

    uploaded_roms = []
    skipped_roms = []

    for rom in roms:
        roms_path = get_fs_structure(platform_fs_slug)
        if _file_exists(roms_path, rom.filename):
            log.warning(f" - Skipping {rom.filename} since the file already exists")
            skipped_roms.append(rom.filename)
            continue

        log.info(f" - Uploading {rom.filename}")
        file_location = f"{roms_path}/{rom.filename}"

        with open(file_location, "wb+") as f:
            while True:
                chunk = rom.file.read(1024)
                if not chunk:
                    break
                f.write(chunk)

        uploaded_roms.append(rom.filename)

    return {
        "uploaded_roms": uploaded_roms,
        "skipped_roms": skipped_roms,
    }


@protected_route(router.get, "/roms/{id}/download", ["roms.read"])
def download_rom(
    request: Request, id: int, files: Annotated[list[str] | None, Query()] = None
):
    """Downloads a rom or a zip file with multiple roms"""
    rom = dbh.get_rom(id)
    rom_path = f"{LIBRARY_BASE_PATH}/{rom.full_path}"

    if not rom.multi:
        return FileResponse(path=rom_path, filename=rom.file_name)

    # Builds a generator of tuples for each member file
    def local_files():
        def contents(file_name):
            try:
                with open(f"{rom_path}/{file_name}", "rb") as f:
                    while chunk := f.read(65536):
                        yield chunk
            except FileNotFoundError:
                log.error(f"File {rom_path}/{file_name} not found!")

        return [
            (file_name, datetime.now(), S_IFREG | 0o600, ZIP_64, contents(file_name))
            for file_name in files
        ]

    zipped_chunks = stream_zip(local_files())

    # Streams the zip file to the client
    return CustomStreamingResponse(
        zipped_chunks,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={rom.name}.zip"},
        emit_body={"id": rom.id},
    )


@protected_route(router.get, "/platforms/{platform_slug}/roms", ["roms.read"])
def roms(
    request: Request,
    platform_slug: str,
    size: int = 60,
    cursor: str = "",
    search_term: str = "",
) -> CursorPage[RomSchema]:
    """Returns all roms of the desired platform"""
    with dbh.session.begin() as session:
        cursor_params = CursorParams(size=size, cursor=cursor)
        qq = dbh.get_roms(platform_slug)

        if search_term:
            return paginate(
                session,
                qq.filter(Rom.file_name.ilike(f"%{search_term}%")),
                cursor_params,
            )

        return paginate(session, qq, cursor_params)


@protected_route(router.patch, "/roms/{id}", ["roms.write"])
async def update_rom(
    request: Request,
    id: int,
    rename_as_igdb: bool = False,
    artwork: Optional[UploadFile] = File(None),
) -> RomSchema:
    """Updates rom details"""

    data = await request.form()

    db_rom = dbh.get_rom(id)
    platform_fs_slug = dbh.get_platform(db_rom.platform_slug).fs_slug

    cleaned_data = {}
    cleaned_data["igdb_id"] = data.get("igdb_id", db_rom.igdb_id) or None
    cleaned_data["name"] = data.get("name", db_rom.name)
    cleaned_data["slug"] = data.get("slug", db_rom.slug)
    cleaned_data["summary"] = data.get("summary", db_rom.summary)
    cleaned_data["url_cover"] = data.get("url_cover", db_rom.url_cover)
    cleaned_data["url_screenshots"] = json.loads(data["url_screenshots"])

    fs_safe_file_name = (
        data.get("file_name", db_rom.file_name).strip().replace("/", "-")
    )
    fs_safe_name = cleaned_data["name"].strip().replace("/", "-")

    if rename_as_igdb:
        fs_safe_file_name = db_rom.file_name.replace(
            db_rom.file_name_no_tags, fs_safe_name
        )

    try:
        if db_rom.file_name != fs_safe_file_name:
            rename_file(platform_fs_slug, db_rom.file_name, fs_safe_file_name)
    except RomAlreadyExistsException as e:
        log.error(str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    cleaned_data["file_name"] = fs_safe_file_name
    cleaned_data["file_name_no_tags"] = get_file_name_with_no_tags(fs_safe_file_name)
    cleaned_data.update(
        get_rom_cover(
            overwrite=True,
            fs_slug=platform_fs_slug,
            rom_name=cleaned_data["name"],
            url_cover=cleaned_data.get("url_cover", ""),
        )
    )

    cleaned_data.update(
        get_rom_screenshots(
            fs_slug=platform_fs_slug,
            rom_name=cleaned_data["name"],
            url_screenshots=cleaned_data.get("url_screenshots", []),
        ),
    )

    if artwork is not None:
        file_ext = artwork.filename.split(".")[-1]
        path_cover_l, path_cover_s, artwork_path = build_artwork_path(
            cleaned_data["name"], platform_fs_slug, file_ext
        )

        cleaned_data["path_cover_l"] = path_cover_l
        cleaned_data["path_cover_s"] = path_cover_s

        artwork_file = artwork.file.read()
        file_location_s = f"{artwork_path}/small.{file_ext}"
        with open(file_location_s, "wb+") as artwork_s:
            artwork_s.write(artwork_file)

        file_location_l = f"{artwork_path}/big.{file_ext}"
        with open(file_location_l, "wb+") as artwork_l:
            artwork_l.write(artwork_file)

    dbh.update_rom(id, cleaned_data)

    return dbh.get_rom(id)


def _delete_single_rom(rom_id: int, delete_from_fs: bool = False):
    rom = dbh.get_rom(rom_id)
    if not rom:
        error = f"Rom with id {rom_id} not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    log.info(f"Deleting {rom.file_name} from database")
    dbh.delete_rom(rom_id)

    if delete_from_fs:
        log.info(f"Deleting {rom.file_name} from filesystem")
        try:
            remove_file(rom.platform_slug, rom.file_name)
        except FileNotFoundError:
            error = f"Rom file {rom.file_name} not found for platform {rom.platform_slug}"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)
    return rom


class DeleteRomResponse(TypedDict):
    msg: str


@protected_route(router.delete, "/roms/{id}", ["roms.write"])
def delete_rom(
    request: Request, id: int, delete_from_fs: bool = False
) -> DeleteRomResponse:
    """Detele rom from database [and filesystem]"""

    rom = _delete_single_rom(id, delete_from_fs)

    return {"msg": f"{rom.file_name} deleted successfully!"}


class MassDeleteRomResponse(TypedDict):
    msg: str


@protected_route(router.post, "/roms/delete", ["roms.write"])
async def delete_roms(
    request: Request,
    delete_from_fs: bool = False,
) -> MassDeleteRomResponse:
    """Detele multiple roms from database [and filesystem]"""

    data: dict = await request.json()
    roms_ids: list = data["roms"]

    for rom_id in roms_ids:
        _delete_single_rom(rom_id, delete_from_fs)

    return {"msg": f"{len(roms_ids)} roms deleted successfully!"}
