import binascii
from base64 import b64encode
from shutil import rmtree
from typing import Annotated
from urllib.parse import quote

from anyio import Path, open_file
from config import (
    DISABLE_DOWNLOAD_ENDPOINT_AUTH,
    LIBRARY_BASE_PATH,
    RESOURCES_BASE_PATH,
)
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.rom import DetailedRomSchema, RomUserSchema, SimpleRomSchema
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from exceptions.fs_exceptions import RomAlreadyExistsException
from fastapi import HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from handler.database import db_platform_handler, db_rom_handler
from handler.filesystem import fs_resource_handler, fs_rom_handler
from handler.filesystem.base_handler import CoverSize
from handler.metadata import meta_igdb_handler, meta_moby_handler
from logger.logger import log
from starlette.requests import ClientDisconnect
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, NullTarget
from utils.filesystem import sanitize_filename
from utils.hashing import crc32_to_hex
from utils.nginx import ZipContentLine, ZipResponse
from utils.router import APIRouter

router = APIRouter()


@protected_route(router.post, "/roms", ["roms.write"])
async def add_rom(request: Request):
    """Upload single rom endpoint

    Args:
        request (Request): Fastapi Request object

    Raises:
        HTTPException: No files were uploaded
    """
    platform_id = request.headers.get("x-upload-platform")
    filename = request.headers.get("x-upload-filename")
    if not platform_id or not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No platform ID or filename provided",
        ) from None

    db_platform = db_platform_handler.get_platform(int(platform_id))
    if not db_platform:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform not found",
        ) from None

    platform_fs_slug = db_platform.fs_slug
    roms_path = fs_rom_handler.build_upload_file_path(platform_fs_slug)
    log.info(f"Uploading file to {platform_fs_slug}")

    file_location = Path(f"{roms_path}/{filename}")
    parser = StreamingFormDataParser(headers=request.headers)
    parser.register("x-upload-platform", NullTarget())
    parser.register(filename, FileTarget(str(file_location)))

    if await file_location.exists():
        log.warning(f" - Skipping {filename} since the file already exists")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File {filename} already exists",
        ) from None

    async def cleanup_partial_file():
        if await file_location.exists():
            await file_location.unlink()

    try:
        async for chunk in request.stream():
            parser.data_received(chunk)
    except ClientDisconnect:
        log.error("Client disconnected during upload")
        await cleanup_partial_file()
    except Exception as exc:
        log.error("Error uploading files", exc_info=exc)
        await cleanup_partial_file()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the file(s)",
        ) from exc

    return Response(status_code=status.HTTP_201_CREATED)


@protected_route(router.get, "/roms", ["roms.read"])
def get_roms(
    request: Request,
    platform_id: int | None = None,
    collection_id: int | None = None,
    search_term: str = "",
    limit: int | None = None,
    order_by: str = "name",
    order_dir: str = "asc",
) -> list[SimpleRomSchema]:
    """Get roms endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Rom internal id

    Returns:
        list[SimpleRomSchema]: List of roms stored in the database
    """

    roms = db_rom_handler.get_roms(
        platform_id=platform_id,
        collection_id=collection_id,
        search_term=search_term.lower(),
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
        limit=limit,
    )

    return [SimpleRomSchema.from_orm_with_request(rom, request) for rom in roms]


@protected_route(
    router.get,
    "/roms/{id}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else ["roms.read"],
)
def get_rom(request: Request, id: int) -> DetailedRomSchema:
    """Get rom endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id

    Returns:
        DetailedRomSchema: Rom stored in the database
    """

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    return DetailedRomSchema.from_orm_with_request(rom, request)


@protected_route(
    router.head,
    "/roms/{id}/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else ["roms.read"],
)
async def head_rom_content(
    request: Request,
    id: int,
    file_name: str,
    files: Annotated[list[str] | None, Query()] = None,
):
    """Head rom content endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id
        file_name (str): Required due to a bug in emulatorjs

    Returns:
        FileResponse: Returns the response with headers
    """

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    files_to_check = files or [r["filename"] for r in rom.files]

    if not rom.multi:
        return Response(
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{quote(rom.file_name)}"',
                "X-Accel-Redirect": f"/library/{rom.full_path}",
            },
        )

    if len(files_to_check) == 1:
        return Response(
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{quote(files_to_check[0])}"',
                "X-Accel-Redirect": f"/library/{rom.full_path}/{files_to_check[0]}",
            },
        )

    return Response(
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{quote(file_name)}.zip"',
        },
    )


@protected_route(
    router.get,
    "/roms/{id}/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else ["roms.read"],
)
async def get_rom_content(
    request: Request,
    id: int,
    file_name: str,
    files: Annotated[list[str] | None, Query()] = None,
):
    """Download rom endpoint (one single file or multiple zipped files for multi-part roms)

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id
        files (Annotated[list[str]  |  None, Query, optional): List of files to download for multi-part roms. Defaults to None.

    Returns:
        FileResponse: Returns one file for single file roms

    Yields:
        ZipResponse: Returns a response for nginx to serve a Zip file for multi-part roms
    """

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    rom_path = f"{LIBRARY_BASE_PATH}/{rom.full_path}"
    files_to_download = sorted(files or [r["filename"] for r in rom.files])

    if not rom.multi:
        return Response(
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{quote(rom.file_name)}"',
                "X-Accel-Redirect": f"/library/{rom.full_path}",
            },
        )

    if len(files_to_download) == 1:
        return Response(
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{quote(files_to_download[0])}"',
                "X-Accel-Redirect": f"/library/{rom.full_path}/{files_to_download[0]}",
            },
        )

    content_lines = [
        ZipContentLine(
            # TODO: Use calculated CRC-32 if available.
            crc32=None,
            size_bytes=(await Path(f"{rom_path}/{f}").stat()).st_size,
            encoded_location=quote(f"/library-zip/{rom.full_path}/{f}"),
            filename=f,
        )
        for f in files_to_download
    ]

    m3u_encoded_content = "\n".join([f for f in files_to_download]).encode()
    m3u_base64_content = b64encode(m3u_encoded_content).decode()
    m3u_line = ZipContentLine(
        crc32=crc32_to_hex(binascii.crc32(m3u_encoded_content)),
        size_bytes=len(m3u_encoded_content),
        encoded_location=f"/decode?value={m3u_base64_content}",
        filename=f"{file_name}.m3u",
    )

    return ZipResponse(
        content_lines=content_lines + [m3u_line],
        filename=f"{quote(file_name)}.zip",
    )


@protected_route(router.put, "/roms/{id}", ["roms.write"])
async def update_rom(
    request: Request,
    id: int,
    rename_as_source: bool = False,
    remove_cover: bool = False,
    artwork: UploadFile | None = None,
) -> DetailedRomSchema:
    """Update rom endpoint

    Args:
        request (Request): Fastapi Request object
        id (Rom): Rom internal id
        rename_as_source (bool, optional): Flag to rename rom file as matched IGDB game. Defaults to False.
        artwork (UploadFile, optional): Custom artork to set as cover. Defaults to File(None).

    Raises:
        HTTPException: If a rom already have that name when enabling the rename_as_source flag

    Returns:
        DetailedRomSchema: Rom stored in the database
    """

    data = await request.form()

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    cleaned_data = {
        "igdb_id": data.get("igdb_id", None),
        "moby_id": data.get("moby_id", None),
    }

    if (
        cleaned_data.get("moby_id", "")
        and int(cleaned_data.get("moby_id", "")) != rom.moby_id
    ):
        moby_rom = await meta_moby_handler.get_rom_by_id(cleaned_data["moby_id"])
        cleaned_data.update(moby_rom)
        path_screenshots = await fs_resource_handler.get_rom_screenshots(
            rom=rom,
            url_screenshots=cleaned_data.get("url_screenshots", []),
        )
        cleaned_data.update({"path_screenshots": path_screenshots})

    if (
        cleaned_data.get("igdb_id", "")
        and int(cleaned_data.get("igdb_id", "")) != rom.igdb_id
    ):
        igdb_rom = await meta_igdb_handler.get_rom_by_id(cleaned_data["igdb_id"])
        cleaned_data.update(igdb_rom)
        path_screenshots = await fs_resource_handler.get_rom_screenshots(
            rom=rom,
            url_screenshots=cleaned_data.get("url_screenshots", []),
        )
        cleaned_data.update({"path_screenshots": path_screenshots})

    cleaned_data.update(
        {
            "name": data.get("name", rom.name),
            "summary": data.get("summary", rom.summary),
        }
    )

    new_file_name = data.get("file_name", rom.file_name)

    try:
        if rename_as_source:
            new_file_name = rom.file_name.replace(
                rom.file_name_no_tags or rom.file_name_no_ext,
                data.get("name", rom.name),
            )
            new_file_name = sanitize_filename(new_file_name)
            fs_rom_handler.rename_file(
                old_name=rom.file_name,
                new_name=new_file_name,
                file_path=rom.file_path,
            )
        elif rom.file_name != new_file_name:
            new_file_name = sanitize_filename(new_file_name)
            fs_rom_handler.rename_file(
                old_name=rom.file_name,
                new_name=new_file_name,
                file_path=rom.file_path,
            )
    except RomAlreadyExistsException as exc:
        log.error(exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc
        ) from exc

    cleaned_data.update(
        {
            "file_name": new_file_name,
            "file_name_no_tags": fs_rom_handler.get_file_name_with_no_tags(
                new_file_name
            ),
            "file_name_no_ext": fs_rom_handler.get_file_name_with_no_extension(
                new_file_name
            ),
        }
    )

    if remove_cover:
        cleaned_data.update(fs_resource_handler.remove_cover(rom))
        cleaned_data.update({"url_cover": ""})
    else:
        if artwork:
            file_ext = artwork.filename.split(".")[-1]
            (
                path_cover_l,
                path_cover_s,
                artwork_path,
            ) = await fs_resource_handler.build_artwork_path(rom, file_ext)

            cleaned_data.update(
                {"path_cover_s": path_cover_s, "path_cover_l": path_cover_l}
            )

            artwork_file = artwork.file.read()
            file_location_s = f"{artwork_path}/small.{file_ext}"
            async with await open_file(file_location_s, "wb+") as artwork_s:
                await artwork_s.write(artwork_file)
                fs_resource_handler.resize_cover_to_small(file_location_s)

            file_location_l = f"{artwork_path}/big.{file_ext}"
            async with await open_file(file_location_l, "wb+") as artwork_l:
                await artwork_l.write(artwork_file)
            cleaned_data.update({"url_cover": ""})
        else:
            if data.get("url_cover", "") != rom.url_cover or not (
                await fs_resource_handler.cover_exists(rom, CoverSize.BIG)
            ):
                cleaned_data.update({"url_cover": data.get("url_cover", rom.url_cover)})
                path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
                    overwrite=True,
                    entity=rom,
                    url_cover=data.get("url_cover", ""),
                )
                cleaned_data.update(
                    {"path_cover_s": path_cover_s, "path_cover_l": path_cover_l}
                )

    db_rom_handler.update_rom(id, cleaned_data)

    return DetailedRomSchema.from_orm_with_request(db_rom_handler.get_rom(id), request)


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
    delete_from_fs: list = data["delete_from_fs"]

    for id in roms_ids:
        rom = db_rom_handler.get_rom(id)

        if not rom:
            raise RomNotFoundInDatabaseException(id)

        log.info(f"Deleting {rom.file_name} from database")
        db_rom_handler.delete_rom(id)

        try:
            rmtree(f"{RESOURCES_BASE_PATH}/{rom.fs_resources_path}")
        except FileNotFoundError:
            log.error(f"Couldn't find resources to delete for {rom.name}")

        if id in delete_from_fs:
            log.info(f"Deleting {rom.file_name} from filesystem")
            try:
                fs_rom_handler.remove_file(
                    file_name=rom.file_name, file_path=rom.file_path
                )
            except FileNotFoundError as exc:
                error = f"Rom file {rom.file_name} not found for platform {rom.platform_slug}"
                log.error(error)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=error
                ) from exc

    return {"msg": f"{len(roms_ids)} roms deleted successfully!"}


@protected_route(router.put, "/roms/{id}/props", ["roms.user.write"])
async def update_rom_user(request: Request, id: int) -> RomUserSchema:
    data = await request.json()

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    db_rom_user = db_rom_handler.get_rom_user(
        id, request.user.id
    ) or db_rom_handler.add_rom_user(id, request.user.id)

    cleaned_data = {
        "note_raw_markdown": data.get(
            "note_raw_markdown", db_rom_user.note_raw_markdown
        ),
        "note_is_public": data.get("note_is_public", db_rom_user.note_is_public),
        "is_main_sibling": data.get("is_main_sibling", db_rom_user.is_main_sibling),
    }

    return db_rom_handler.update_rom_user(db_rom_user.id, cleaned_data)
