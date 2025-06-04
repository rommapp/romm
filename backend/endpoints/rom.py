import binascii
import os
from base64 import b64encode
from datetime import datetime, timezone
from io import BytesIO
from shutil import rmtree
from stat import S_IFREG
from typing import Any, TypeVar
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from anyio import Path, open_file
from config import (
    DEV_MODE,
    DISABLE_DOWNLOAD_ENDPOINT_AUTH,
    LIBRARY_BASE_PATH,
    RESOURCES_BASE_PATH,
    str_to_bool,
)
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.rom import (
    DetailedRomSchema,
    RomFileSchema,
    RomUserSchema,
    SimpleRomSchema,
)
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from exceptions.fs_exceptions import RomAlreadyExistsException
from fastapi import HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.limit_offset import LimitOffsetPage, LimitOffsetParams
from handler.auth.constants import Scope
from handler.database import db_platform_handler, db_rom_handler
from handler.database.base_handler import sync_session
from handler.filesystem import fs_resource_handler, fs_rom_handler
from handler.filesystem.base_handler import CoverSize
from handler.metadata import meta_igdb_handler, meta_moby_handler, meta_ss_handler
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import RomFile
from PIL import Image
from starlette.requests import ClientDisconnect
from starlette.responses import FileResponse
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, NullTarget
from utils.filesystem import sanitize_filename
from utils.hashing import crc32_to_hex
from utils.nginx import FileRedirectResponse, ZipContentLine, ZipResponse
from utils.router import APIRouter

T = TypeVar("T")

router = APIRouter(
    prefix="/roms",
    tags=["roms"],
)


@protected_route(router.post, "", [Scope.ROMS_WRITE])
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
    roms_path = fs_rom_handler.build_upload_fs_path(platform_fs_slug)
    log.info(
        f"Uploading file to {hl(db_platform.custom_name or db_platform.name, color=BLUE)}[{hl(platform_fs_slug)}]"
    )

    file_location = Path(f"{roms_path}/{filename}")
    parser = StreamingFormDataParser(headers=request.headers)
    parser.register("x-upload-platform", NullTarget())
    parser.register(filename, FileTarget(str(file_location)))

    if await file_location.exists():
        log.warning(f" - Skipping {hl(filename)} since the file already exists")
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


class CustomLimitOffsetParams(LimitOffsetParams):
    # Temporarily increase the limit until we can implement pagination on all apps
    limit: int = Query(50, ge=1, le=10_000, description="Page size limit")
    offset: int = Query(0, ge=0, description="Page offset")


class CustomLimitOffsetPage(LimitOffsetPage[T]):
    char_index: dict[str, int]
    __params_type__ = CustomLimitOffsetParams


@protected_route(router.get, "", [Scope.ROMS_READ])
def get_roms(
    request: Request,
    platform_id: int | None = None,
    collection_id: int | None = None,
    virtual_collection_id: str | None = None,
    search_term: str | None = None,
    order_by: str = "name",
    order_dir: str = "asc",
    unmatched_only: bool = False,
    matched_only: bool = False,
    favourites_only: bool = False,
    duplicates_only: bool = False,
    playables_only: bool = False,
    ra_only: bool = False,
    group_by_meta_id: bool = False,
    selected_genre: str | None = None,
    selected_franchise: str | None = None,
    selected_collection: str | None = None,
    selected_company: str | None = None,
    selected_age_rating: str | None = None,
    selected_status: str | None = None,
    selected_region: str | None = None,
    selected_language: str | None = None,
) -> CustomLimitOffsetPage[SimpleRomSchema]:
    """Get roms endpoint

    Args:
        request: Fastapi Request object
        platform_id (int, optional): Platform internal id. Defaults to None.
        collection_id (int, optional): Collection internal id. Defaults to None.
        virtual_collection_id (str, optional): Virtual collection internal id. Defaults to None.
        search_term (str, optional): Search term to filter roms. Defaults to None.
        order_by (str, optional): Field to order by. Defaults to "name".
        order_dir (str, optional): Order direction. Defaults to "asc".
        unmatched_only (bool, optional): Filter only unmatched roms. Defaults to False.
        matched_only (bool, optional): Filter only matched roms. Defaults to False.
        favourites_only (bool, optional): Filter only favourite roms. Defaults to False.
        duplicates_only (bool, optional): Filter only duplicate roms. Defaults to False.
        playables_only (bool, optional): Filter only playable roms by emulatorjs. Defaults to False.
        ra_only (bool, optional): Filter only roms with Retroachievements compatibility.
        group_by_meta_id (bool, optional): Group roms by igdb/moby/ssrf ID. Defaults to False.
        selected_genre (str, optional): Filter by genre. Defaults to None.
        selected_franchise (str, optional): Filter by franchise. Defaults to None.
        selected_collection (str, optional): Filter by collection. Defaults to None.
        selected_company (str, optional): Filter by company. Defaults to None.
        selected_age_rating (str, optional): Filter by age rating. Defaults to None.
        selected_status (str, optional): Filter by status. Defaults to None.
        selected_region (str, optional): Filter by region tag. Defaults to None.
        selected_language (str, optional): Filter by language tag. Defaults to None.

    Returns:
        list[RomSchema | SimpleRomSchema]: List of ROMs stored in the database
    """

    # Get the base roms query
    query = db_rom_handler.get_roms_query(
        user_id=request.user.id,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
    )

    # Filter down the query
    query = db_rom_handler.filter_roms(
        query=query,
        user_id=request.user.id,
        platform_id=platform_id,
        collection_id=collection_id,
        virtual_collection_id=virtual_collection_id,
        search_term=search_term,
        unmatched_only=unmatched_only,
        matched_only=matched_only,
        favourites_only=favourites_only,
        duplicates_only=duplicates_only,
        playables_only=playables_only,
        ra_only=ra_only,
        selected_genre=selected_genre,
        selected_franchise=selected_franchise,
        selected_collection=selected_collection,
        selected_company=selected_company,
        selected_age_rating=selected_age_rating,
        selected_status=selected_status,
        selected_region=selected_region,
        selected_language=selected_language,
        group_by_meta_id=group_by_meta_id,
    )

    # Get the char index for the roms
    char_index = db_rom_handler.get_char_index(query=query)
    char_index_dict = {char: index for (char, index) in char_index}

    with sync_session.begin() as session:
        return paginate(
            session,
            query,
            transformer=lambda items: [
                SimpleRomSchema.from_orm_with_request(i, request) for i in items
            ],
            additional_data={"char_index": char_index_dict},
        )


@protected_route(
    router.get,
    "/{id}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
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
    "/{id}/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
async def head_rom_content(
    request: Request,
    id: int,
    file_name: str,
):
    """Head rom content endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id
        file_name (str): File name to download
        file_ids (list[int]): List of file ids to download for multi-part roms

    Returns:
        FileResponse: Returns the response with headers
    """

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    file_ids = request.query_params.get("file_ids") or ""
    file_ids = [int(f) for f in file_ids.split(",") if f]
    files = [f for f in rom.files if f.id in file_ids or not file_ids]
    files.sort(key=lambda x: x.file_name)

    # Serve the file directly in development mode for emulatorjs
    if DEV_MODE:
        if len(files) == 1:
            file = files[0]
            rom_path = f"{LIBRARY_BASE_PATH}/{file.full_path}"
            return FileResponse(
                path=rom_path,
                filename=file.file_name,
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file.file_name)}; filename=\"{quote(file.file_name)}\"",
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(file.file_size_bytes),
                },
            )

        return Response(
            headers={
                "Content-Type": "application/zip",
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}.zip; filename=\"{quote(file_name)}.zip\"",
            },
        )

    # Otherwise proxy through nginx
    if len(files) == 1:
        return FileRedirectResponse(
            download_path=Path(f"/library/{files[0].full_path}"),
        )

    return Response(
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}.zip; filename=\"{quote(file_name)}.zip\"",
        },
    )


@protected_route(
    router.get,
    "/{id}/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
async def get_rom_content(
    request: Request,
    id: int,
    file_name: str,
):
    """Download rom endpoint (one single file or multiple zipped files for multi-part roms)

    Args:
        request (Request): Fastapi Request object
        id (int): Rom internal id
        file_name: Zip file output name

    Returns:
        Response: Returns a response with headers

    Yields:
        FileResponse: Returns one file for single file roms
        FileRedirectResponse: Redirects to the file download path
        ZipResponse: Returns a response for nginx to serve a Zip file for multi-part roms
    """

    current_username = (
        request.user.username if request.user.is_authenticated else "unknown"
    )
    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    # https://muos.dev/help/addcontent#what-about-multi-disc-content
    hidden_folder = str_to_bool(request.query_params.get("hidden_folder", ""))

    file_ids = request.query_params.get("file_ids") or ""
    file_ids = [int(f) for f in file_ids.split(",") if f]
    files = [f for f in rom.files if f.id in file_ids or not file_ids]
    files.sort(key=lambda x: x.file_name)

    log.info(
        f"User {hl(current_username, color=BLUE)} is downloading {hl(rom.fs_name)}"
    )

    # Serve the file directly in development mode for emulatorjs
    if DEV_MODE:
        if len(files) == 1:
            file = files[0]
            rom_path = f"{LIBRARY_BASE_PATH}/{file.full_path}"
            return FileResponse(
                path=rom_path,
                filename=file.file_name,
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file.file_name)}; filename=\"{quote(file.file_name)}\"",
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(file.file_size_bytes),
                },
            )

        async def build_zip_in_memory() -> bytes:
            # Initialize in-memory buffer
            zip_buffer = BytesIO()
            now = datetime.now()

            with ZipFile(zip_buffer, "w") as zip_file:
                # Add content files
                for file in files:
                    file_path = f"{LIBRARY_BASE_PATH}/{file.full_path}"
                    try:
                        # Read entire file into memory
                        async with await open_file(file_path, "rb") as f:
                            content = await f.read()

                        # Create ZIP info with compression
                        zip_info = ZipInfo(
                            filename=file.file_name_for_download(rom, hidden_folder),
                            date_time=now.timetuple()[:6],
                        )
                        zip_info.external_attr = S_IFREG | 0o600
                        zip_info.compress_type = (
                            ZIP_DEFLATED if file.file_size_bytes > 0 else ZIP_STORED
                        )

                        # Write file to ZIP
                        zip_file.writestr(zip_info, content)

                    except FileNotFoundError:
                        log.error(f"File {hl(file_path)} not found!")
                        raise

                # Add M3U file if not already present
                if not rom.has_m3u_file():
                    m3u_encoded_content = "\n".join(
                        [f.file_name_for_download(rom, hidden_folder) for f in files]
                    ).encode()
                    m3u_filename = f"{rom.fs_name}.m3u"
                    m3u_info = ZipInfo(
                        filename=m3u_filename, date_time=now.timetuple()[:6]
                    )
                    m3u_info.external_attr = S_IFREG | 0o600
                    m3u_info.compress_type = ZIP_STORED
                    zip_file.writestr(m3u_info, m3u_encoded_content)

            # Get the completed ZIP file bytes
            zip_buffer.seek(0)
            return zip_buffer.getvalue()

        zip_data = await build_zip_in_memory()

        # Streams the zip file to the client
        return Response(
            content=zip_data,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}.zip; filename=\"{quote(file_name)}.zip\"",
            },
        )

    # Otherwise proxy through nginx
    if len(files) == 1:
        return FileRedirectResponse(
            download_path=Path(f"/library/{files[0].full_path}"),
        )

    async def create_zip_content(f: RomFile, base_path: str = LIBRARY_BASE_PATH):
        return ZipContentLine(
            crc32=f.crc_hash,
            size_bytes=(await Path(LIBRARY_BASE_PATH, f.full_path).stat()).st_size,
            encoded_location=quote(f"{base_path}/{f.full_path}"),
            filename=f.file_name_for_download(rom, hidden_folder),
        )

    content_lines = [await create_zip_content(f, "/library-zip") for f in files]

    if not rom.has_m3u_file():
        m3u_encoded_content = "\n".join(
            [f.file_name_for_download(rom, hidden_folder) for f in files]
        ).encode()
        m3u_base64_content = b64encode(m3u_encoded_content).decode()
        m3u_line = ZipContentLine(
            crc32=crc32_to_hex(binascii.crc32(m3u_encoded_content)),
            size_bytes=len(m3u_encoded_content),
            encoded_location=f"/decode?value={m3u_base64_content}",
            filename=f"{file_name}.m3u",
        )
        content_lines.append(m3u_line)

    return ZipResponse(
        content_lines=content_lines,
        filename=f"{quote(file_name)}.zip",
    )


@protected_route(router.put, "/{id}", [Scope.ROMS_WRITE])
async def update_rom(
    request: Request,
    id: int,
    remove_cover: bool = False,
    artwork: UploadFile | None = None,
    unmatch_metadata: bool = False,
) -> DetailedRomSchema:
    """Update rom endpoint

    Args:
        request (Request): Fastapi Request object
        id (Rom): Rom internal id
        artwork (UploadFile, optional): Custom artwork to set as cover. Defaults to File(None).
        unmatch_metadata: Remove the metadata matches for this game. Defaults to False.

    Raises:
        HTTPException: Rom not found in database

    Returns:
        DetailedRomSchema: Rom stored in the database
    """

    data = await request.form()

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if unmatch_metadata:
        db_rom_handler.update_rom(
            id,
            {
                "igdb_id": None,
                "sgdb_id": None,
                "moby_id": None,
                "ss_id": None,
                "ra_id": None,
                "name": rom.fs_name,
                "summary": "",
                "url_screenshots": [],
                "path_screenshots": [],
                "path_cover_s": "",
                "path_cover_l": "",
                "url_cover": "",
                "url_manual": "",
                "slug": "",
                "igdb_metadata": {},
                "moby_metadata": {},
                "ss_metadata": {},
                "ra_metadata": {},
                "revision": "",
            },
        )

        rom = db_rom_handler.get_rom(id)
        if not rom:
            raise RomNotFoundInDatabaseException(id)

        return DetailedRomSchema.from_orm_with_request(rom, request)

    cleaned_data: dict[str, Any] = {
        "igdb_id": data.get("igdb_id", rom.igdb_id),
        "moby_id": data.get("moby_id", rom.moby_id),
        "ss_id": data.get("ss_id", rom.ss_id),
    }

    if (
        cleaned_data.get("moby_id", "")
        and int(cleaned_data.get("moby_id", "")) != rom.moby_id
    ):
        moby_rom = await meta_moby_handler.get_rom_by_id(
            int(cleaned_data.get("moby_id", ""))
        )
        cleaned_data.update(moby_rom)
        path_screenshots = await fs_resource_handler.get_rom_screenshots(
            rom=rom,
            url_screenshots=cleaned_data.get("url_screenshots", []),
        )
        cleaned_data.update({"path_screenshots": path_screenshots})

    if (
        cleaned_data.get("ss_id", "")
        and int(cleaned_data.get("ss_id", "")) != rom.ss_id
    ):
        ss_rom = await meta_ss_handler.get_rom_by_id(cleaned_data["ss_id"])
        cleaned_data.update(ss_rom)
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

    new_fs_name = str(data.get("fs_name") or rom.fs_name)
    cleaned_data.update(
        {
            "fs_name": new_fs_name,
            "fs_name_no_tags": fs_rom_handler.get_file_name_with_no_tags(new_fs_name),
            "fs_name_no_ext": fs_rom_handler.get_file_name_with_no_extension(
                new_fs_name
            ),
        }
    )

    if remove_cover:
        cleaned_data.update(fs_resource_handler.remove_cover(rom))
        cleaned_data.update({"url_cover": ""})
    else:
        if artwork is not None and artwork.filename is not None:
            file_ext = artwork.filename.split(".")[-1]
            (
                path_cover_l,
                path_cover_s,
                artwork_path,
            ) = await fs_resource_handler.build_artwork_path(rom, file_ext)

            cleaned_data.update(
                {"path_cover_s": path_cover_s, "path_cover_l": path_cover_l}
            )

            artwork_content = BytesIO(await artwork.read())
            file_location_small = Path(f"{artwork_path}/small.{file_ext}")
            file_location_large = Path(f"{artwork_path}/big.{file_ext}")
            with Image.open(artwork_content) as img:
                img.save(file_location_large)
                fs_resource_handler.resize_cover_to_small(
                    img, save_path=file_location_small
                )

            cleaned_data.update({"url_cover": ""})
        else:
            if data.get("url_cover", "") != rom.url_cover or not (
                await fs_resource_handler.cover_exists(rom, CoverSize.BIG)
            ):
                cleaned_data.update({"url_cover": data.get("url_cover", rom.url_cover)})
                path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
                    entity=rom,
                    overwrite=True,
                    url_cover=str(data.get("url_cover") or ""),
                )
                cleaned_data.update(
                    {"path_cover_s": path_cover_s, "path_cover_l": path_cover_l}
                )

    if data.get("url_manual", "") != rom.url_manual or not (
        await fs_resource_handler.manual_exists(rom)
    ):
        cleaned_data.update({"url_manual": data.get("url_manual", rom.url_manual)})
        path_manual = await fs_resource_handler.get_manual(
            rom=rom,
            overwrite=True,
            url_manual=str(data.get("url_manual") or ""),
        )
        cleaned_data.update({"path_manual": path_manual})

    log.debug(
        f"Updating {hl(cleaned_data.get('name', ''), color=BLUE)} [{hl(cleaned_data.get('fs_name', ''))}] with data {cleaned_data}"
    )

    db_rom_handler.update_rom(id, cleaned_data)

    # Rename the file/folder if the name has changed
    should_update_fs = new_fs_name != rom.fs_name
    if should_update_fs:
        try:
            new_fs_name = sanitize_filename(new_fs_name)
            fs_rom_handler.rename_fs_rom(
                old_name=rom.fs_name,
                new_name=new_fs_name,
                fs_path=rom.fs_path,
            )
        except RomAlreadyExistsException as exc:
            log.error(exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc
            ) from exc

    # Update the rom files with the new fs_name
    if should_update_fs:
        for file in rom.files:
            db_rom_handler.update_rom_file(
                file.id,
                {
                    "file_name": file.file_name.replace(rom.fs_name, new_fs_name),
                    "file_path": file.file_path.replace(rom.fs_name, new_fs_name),
                },
            )

    # Refetch the rom from the database
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    return DetailedRomSchema.from_orm_with_request(rom, request)


@protected_route(router.post, "/{id}/manuals", [Scope.ROMS_WRITE])
async def add_rom_manuals(request: Request, id: int):
    """Upload manuals for a rom

    Args:
        request (Request): Fastapi Request object

    Raises:
        HTTPException: No files were uploaded
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    filename = request.headers.get("x-upload-filename", "")

    manuals_path = f"{RESOURCES_BASE_PATH}/{rom.fs_resources_path}/manual"
    file_location = Path(f"{manuals_path}/{rom.id}.pdf")
    log.info(f"Uploading {hl(str(file_location))}")

    if not os.path.exists(manuals_path):
        await Path(manuals_path).mkdir(parents=True, exist_ok=True)

    parser = StreamingFormDataParser(headers=request.headers)
    parser.register("x-upload-platform", NullTarget())
    parser.register(filename, FileTarget(str(file_location)))

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

    path_manual = await fs_resource_handler.get_manual(
        rom=rom, overwrite=False, url_manual=None
    )

    db_rom_handler.update_rom(id, {"path_manual": path_manual})

    return Response(status_code=status.HTTP_201_CREATED)


@protected_route(router.post, "/delete", [Scope.ROMS_WRITE])
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

        log.info(
            f"Deleting {hl(str(rom.name), color=BLUE)} [{hl(rom.fs_name)}] from database"
        )
        db_rom_handler.delete_rom(id)

        try:
            rmtree(f"{RESOURCES_BASE_PATH}/{rom.fs_resources_path}")
        except FileNotFoundError:
            log.error(
                f"Couldn't find resources to delete for {hl(str(rom.name), color=BLUE)}"
            )

        if id in delete_from_fs:
            log.info(f"Deleting {hl(rom.fs_name)} from filesystem")
            try:
                fs_rom_handler.remove_from_fs(fs_path=rom.fs_path, fs_name=rom.fs_name)
            except FileNotFoundError as exc:
                error = f"Rom file {hl(rom.fs_name)} not found for platform {hl(rom.platform_display_name, color=BLUE)}[{hl(rom.platform_slug)}]"
                log.error(error)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=error
                ) from exc

    return {"msg": f"{len(roms_ids)} roms deleted successfully!"}


@protected_route(router.put, "/{id}/props", [Scope.ROMS_USER_WRITE])
async def update_rom_user(request: Request, id: int) -> RomUserSchema:
    data = await request.json()
    rom_user_data = data.get("data", {})

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    db_rom_user = db_rom_handler.get_rom_user(
        id, request.user.id
    ) or db_rom_handler.add_rom_user(id, request.user.id)

    fields_to_update = [
        "note_raw_markdown",
        "note_is_public",
        "is_main_sibling",
        "backlogged",
        "now_playing",
        "hidden",
        "rating",
        "difficulty",
        "completion",
        "status",
    ]

    cleaned_data = {
        field: rom_user_data[field]
        for field in fields_to_update
        if field in rom_user_data
    }

    if data.get("update_last_played", False):
        cleaned_data.update({"last_played": datetime.now(timezone.utc)})
    elif data.get("remove_last_played", False):
        cleaned_data.update({"last_played": None})

    rom_user = db_rom_handler.update_rom_user(db_rom_user.id, cleaned_data)

    return RomUserSchema.model_validate(rom_user)


@protected_route(
    router.get,
    "files/{id}",
    [Scope.ROMS_READ],
)
async def get_romfile(
    request: Request,
    id: int,
) -> RomFileSchema:
    file = db_rom_handler.get_rom_file_by_id(id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return RomFileSchema.model_validate(file)


@protected_route(
    router.get,
    "files/{id}/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
)
async def get_romfile_content(
    request: Request,
    id: int,
    file_name: str,
):
    """Download rom file endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): RomFile internal id
        file_name (str): What to name the file when downloading

    Returns:
        FileResponse: Returns the response with headers
    """

    current_username = (
        request.user.username if request.user.is_authenticated else "unknown"
    )

    file = db_rom_handler.get_rom_file_by_id(id)
    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    log.info(f"User {hl(current_username, color=BLUE)} is downloading {hl(file_name)}")

    # Serve the file directly in development mode for emulatorjs
    if DEV_MODE:
        rom_path = f"{LIBRARY_BASE_PATH}/{file.full_path}"
        return FileResponse(
            path=rom_path,
            filename=file_name,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(file_name)}; filename=\"{quote(file_name)}\"",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(file.file_size_bytes),
            },
        )

    # Otherwise proxy through nginx
    return FileRedirectResponse(
        download_path=Path(f"/library/{file.full_path}"),
    )
