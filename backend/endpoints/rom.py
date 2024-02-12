from datetime import datetime
from stat import S_IFREG
from typing import Annotated, Optional

from config import LIBRARY_BASE_PATH
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.rom import (
    AddRomsResponse,
    CustomStreamingResponse,
    RomSchema,
)
from exceptions.fs_exceptions import RomAlreadyExistsException
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from fastapi_pagination.cursor import CursorPage, CursorParams
from fastapi_pagination.ext.sqlalchemy import paginate
from handler import (
    db_platform_handler,
    db_rom_handler,
    fs_resource_handler,
    fs_rom_handler,
    igdb_handler,
)
from handler.fs_handler import CoverSize
from logger.logger import log
from stream_zip import ZIP_64, stream_zip  # type: ignore[import]

router = APIRouter()


@protected_route(router.post, "/roms", ["roms.write"])
def add_roms(
    request: Request, platform_id: int, roms: list[UploadFile] = File(...)
) -> AddRomsResponse:
    """Upload roms endpoint (one or more at the same time)

    Args:
        request (Request): Fastapi Request object
        platform_slug (str): Slug of the platform where to upload the roms
        roms (list[UploadFile], optional): List of files to upload. Defaults to File(...).

    Raises:
        HTTPException: No files were uploaded

    Returns:
        UploadRomResponse: Standard message response
    """

    platform_fs_slug = db_platform_handler.get_platforms(platform_id).fs_slug
    log.info(f"Uploading roms to {platform_fs_slug}")
    if roms is None:
        log.error("No roms were uploaded")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No roms were uploaded",
        )

    roms_path = fs_rom_handler.build_upload_file_path(platform_fs_slug)

    uploaded_roms = []
    skipped_roms = []

    for rom in roms:
        if fs_rom_handler.file_exists(roms_path, rom.filename):
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


@protected_route(router.get, "/roms", ["roms.read"])
def get_roms(
    request: Request,
    platform_id: int = None,
    size: int = 60,
    cursor: str = "",
    search_term: str = "",
    order_by: str = "name",
    order_dir: str = "asc",
) -> CursorPage[RomSchema]:
    """Get roms endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Rom internal id

    Returns:
        RomSchema: Rom stored in the database
    """

    with db_rom_handler.session.begin() as session:
        cursor_params = CursorParams(size=size, cursor=cursor)
        qq = db_rom_handler.get_roms(
            platform_id=platform_id,
            search_term=search_term.lower(),
            order_by=order_by.lower(),
            order_dir=order_dir.lower(),
        )
        return paginate(session, qq, cursor_params)


@protected_route(router.get, "/roms/{id}", ["roms.read"])
def get_rom(request: Request, id: int) -> RomSchema:
    """Get rom endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id

    Returns:
        RomSchema: Rom stored in the database
    """
    return RomSchema.from_orm_with_request(db_rom_handler.get_roms(id), request)


@protected_route(router.head, "/roms/{id}/content", ["roms.read"])
def head_rom_content(request: Request, id: int):
    """Head rom content endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id

    Returns:
        FileResponse: Returns the response with headers
    """

    rom = db_rom_handler.get_roms(id)
    rom_path = f"{LIBRARY_BASE_PATH}/{rom.full_path}"

    return FileResponse(
        path=rom_path if not rom.multi else f"{rom_path}/{rom.files[0]}",
        filename=rom.file_name,
        headers={
            "Content-Disposition": f"attachment; filename={rom.name}.zip",
            "Content-Type": "application/zip",
            "Content-Length": str(rom.file_size_bytes),
        },
    )


@protected_route(router.get, "/roms/{id}/content", ["roms.read"])
def get_rom_content(
    request: Request, id: int, files: Annotated[list[str] | None, Query()] = None
):
    """Download rom endpoint (one single file or multiple zipped files for multi-part roms)

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id
        files (Annotated[list[str]  |  None, Query, optional): List of files to download for multi-part roms. Defaults to None.

    Returns:
        FileResponse: Returns one file for single file roms

    Yields:
        CustomStreamingResponse: Streams a file for multi-part roms
    """

    rom = db_rom_handler.get_roms(id)
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
            for file_name in rom.files
        ] + [
            (
                f"{rom.file_name}.m3u",
                datetime.now(),
                S_IFREG | 0o600,
                ZIP_64,
                [str.encode(f"{rom.files[i]}\n") for i in range(len(rom.files))],
            )
        ]

    zipped_chunks = stream_zip(local_files())

    # Streams the zip file to the client
    return CustomStreamingResponse(
        zipped_chunks,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={rom.file_name}.zip"},
        emit_body={"id": rom.id},
    )


@protected_route(router.put, "/roms/{id}", ["roms.write"])
async def update_rom(
    request: Request,
    id: int,
    rename_as_igdb: bool = False,
    artwork: Optional[UploadFile] = File(None),
) -> RomSchema:
    """Update rom endpoint

    Args:
        request (Request): Fastapi Request object
        id (Rom): Rom internal id
        rename_as_igdb (bool, optional): Flag to rename rom file as matched IGDB game. Defaults to False.
        artwork (Optional[UploadFile], optional): Custom artork to set as cover. Defaults to File(None).

    Raises:
        HTTPException: If a rom already have that name when enabling the rename_as_igdb flag

    Returns:
        RomSchema: Rom stored in the database
    """

    data = await request.form()

    db_rom = db_rom_handler.get_roms(id)
    platform_fs_slug = db_platform_handler.get_platforms(db_rom.platform_id).fs_slug

    cleaned_data = {}
    cleaned_data["igdb_id"] = data.get("igdb_id", db_rom.igdb_id) or None

    if cleaned_data["igdb_id"]:
        igdb_rom = igdb_handler.get_rom_by_id(cleaned_data["igdb_id"])
        cleaned_data.update(igdb_rom)

    cleaned_data["name"] = data.get("name", db_rom.name)
    cleaned_data["summary"] = data.get("summary", db_rom.summary)

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
            fs_rom_handler.rename_file(
                old_name=db_rom.file_name,
                new_name=fs_safe_file_name,
                file_path=db_rom.file_path,
            )
    except RomAlreadyExistsException as e:
        log.error(str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    cleaned_data["file_name"] = fs_safe_file_name
    cleaned_data["file_name_no_tags"] = fs_rom_handler.get_file_name_with_no_tags(
        fs_safe_file_name
    )
    cleaned_data["file_name_no_ext"] = fs_rom_handler.get_file_name_with_no_extension(
        fs_safe_file_name
    )
    cleaned_data.update(
        fs_resource_handler.get_rom_cover(
            overwrite=True,
            platform_fs_slug=platform_fs_slug,
            rom_name=cleaned_data["name"],
            url_cover=cleaned_data.get("url_cover", ""),
        )
    )

    cleaned_data.update(
        fs_resource_handler.get_rom_screenshots(
            platform_fs_slug=platform_fs_slug,
            rom_name=cleaned_data["name"],
            url_screenshots=cleaned_data.get("url_screenshots", []),
        ),
    )

    if artwork is not None:
        file_ext = artwork.filename.split(".")[-1]
        (
            path_cover_l,
            path_cover_s,
            artwork_path,
        ) = fs_resource_handler.build_artwork_path(
            cleaned_data["name"], platform_fs_slug, file_ext
        )

        cleaned_data["path_cover_l"] = path_cover_l
        cleaned_data["path_cover_s"] = path_cover_s

        artwork_file = artwork.file.read()
        file_location_s = f"{artwork_path}/small.{file_ext}"
        with open(file_location_s, "wb+") as artwork_s:
            artwork_s.write(artwork_file)
        fs_resource_handler.resize_cover(file_location_s, CoverSize.SMALL)

        file_location_l = f"{artwork_path}/big.{file_ext}"
        with open(file_location_l, "wb+") as artwork_l:
            artwork_l.write(artwork_file)
        fs_resource_handler.resize_cover(file_location_l, CoverSize.BIG)

    db_rom_handler.update_rom(id, cleaned_data)

    return db_rom_handler.get_roms(id)


@protected_route(router.post, "/roms/delete", ["roms.write"])
async def delete_roms(
    request: Request,
) -> MessageResponse:
    """Delete roms endpoint

    Args:
        request (Request): Fastapi Request object.
            {
                "roms": List of rom's ids to delete
            }
        delete_from_fs (bool, optional): Flag to delete rom from filesystem. Defaults to False.

    Returns:
        MessageResponse: Standard message response
    """

    data: dict = await request.json()
    roms_ids: list = data["roms"]
    delete_from_fs: bool = data["delete_from_fs"]

    for id in roms_ids:
        rom = db_rom_handler.get_roms(id)
        if not rom:
            error = f"Rom with id {id} not found"
            log.error(error)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

        log.info(f"Deleting {rom.file_name} from database")
        db_rom_handler.delete_rom(id)

        if delete_from_fs:
            log.info(f"Deleting {rom.file_name} from filesystem")
            try:
                fs_rom_handler.remove_file(
                    file_name=rom.file_name, file_path=rom.file_path
                )
            except FileNotFoundError:
                error = f"Rom file {rom.file_name} not found for platform {rom.platform_slug}"
                log.error(error)
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return {"msg": f"{len(roms_ids)} roms deleted successfully!"}
