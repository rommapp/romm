import binascii
import json
from base64 import b64encode
from datetime import datetime, timezone
from io import BytesIO
from stat import S_IFREG
from typing import Annotated, Any
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from anyio import Path, open_file
from fastapi import (
    Body,
    File,
    Header,
    HTTPException,
)
from fastapi import Path as PathVar
from fastapi import (
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.datastructures import FormData
from fastapi.responses import Response
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination.limit_offset import LimitOffsetPage, LimitOffsetParams
from pydantic import BaseModel
from starlette.requests import ClientDisconnect
from starlette.responses import FileResponse
from streaming_form_data import StreamingFormDataParser
from streaming_form_data.targets import FileTarget, NullTarget

from config import (
    DEV_MODE,
    DISABLE_DOWNLOAD_ENDPOINT_AUTH,
    LIBRARY_BASE_PATH,
)
from decorators.auth import protected_route
from endpoints.responses import BulkOperationResponse
from endpoints.responses.rom import (
    DetailedRomSchema,
    RomFileSchema,
    RomUserSchema,
    SimpleRomSchema,
    UserNoteSchema,
)
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from exceptions.fs_exceptions import RomAlreadyExistsException
from handler.auth.constants import Scope
from handler.database import db_platform_handler, db_rom_handler
from handler.database.base_handler import sync_session
from handler.filesystem import fs_resource_handler, fs_rom_handler
from handler.filesystem.base_handler import CoverSize
from handler.metadata import (
    meta_flashpoint_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_ra_handler,
    meta_ss_handler,
)
from handler.metadata.ss_handler import get_preferred_media_types
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.rom import Rom
from utils.database import safe_int, safe_str_to_bool
from utils.filesystem import sanitize_filename
from utils.hashing import crc32_to_hex
from utils.nginx import FileRedirectResponse, ZipContentLine, ZipResponse
from utils.router import APIRouter

router = APIRouter(
    prefix="/roms",
    tags=["roms"],
)


def safe_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None

    return safe_int(value)


def parse_raw_metadata(data: FormData, form_key: str) -> dict | None:
    raw_json = data.get(form_key, None)
    if not raw_json or str(raw_json).strip() == "":
        return None

    try:
        return json.loads(str(raw_json))
    except json.JSONDecodeError as e:
        log.warning(f"Invalid JSON for {form_key}: {e}")
        return None


@protected_route(
    router.post,
    "",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_400_BAD_REQUEST: {}},
)
async def add_rom(
    request: Request,
    platform_id: Annotated[
        int,
        Header(description="Platform internal id.", ge=1, alias="x-upload-platform"),
    ],
    filename: Annotated[
        str,
        Header(
            description="The name of the file being uploaded.",
            alias="x-upload-filename",
        ),
    ],
) -> Response:
    """Upload a single rom."""

    if not platform_id or not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No platform ID or filename provided",
        )

    db_platform = db_platform_handler.get_platform(platform_id)
    if not db_platform:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Platform not found",
        )

    platform_fs_slug = db_platform.fs_slug
    roms_path = fs_rom_handler.get_roms_fs_structure(platform_fs_slug)
    log.info(
        f"Uploading file to {hl(db_platform.custom_name or db_platform.name, color=BLUE)}[{hl(platform_fs_slug)}]"
    )

    file_location = fs_rom_handler.validate_path(f"{roms_path}/{filename}")

    parser = StreamingFormDataParser(headers=request.headers)
    parser.register("x-upload-platform", NullTarget())
    parser.register(filename, FileTarget(str(file_location)))

    # Check if the file already exists
    if await fs_rom_handler.file_exists(f"{roms_path}/{filename}"):
        log.warning(f" - Skipping {hl(filename)} since the file already exists")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File {filename} already exists",
        )

    # Create the directory if it doesn't exist
    await fs_rom_handler.make_directory(roms_path)

    def cleanup_partial_file():
        if file_location.exists():
            file_location.unlink()

    try:
        async for chunk in request.stream():
            parser.data_received(chunk)
    except ClientDisconnect:
        log.error("Client disconnected during upload")
        cleanup_partial_file()
    except Exception as exc:
        log.error("Error uploading files", exc_info=exc)
        cleanup_partial_file()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the file(s)",
        ) from exc

    return Response()


class CustomLimitOffsetParams(LimitOffsetParams):
    # Temporarily increase the limit until we can implement pagination on all apps
    limit: int = Query(50, ge=1, le=10_000, description="Page size limit")
    offset: int = Query(0, ge=0, description="Page offset")


class CustomLimitOffsetPage[T: BaseModel](LimitOffsetPage[T]):
    char_index: dict[str, int]
    rom_id_index: list[int]
    __params_type__ = CustomLimitOffsetParams


@protected_route(router.get, "", [Scope.ROMS_READ])
def get_roms(
    request: Request,
    with_char_index: Annotated[
        bool,
        Query(description="Whether to get the char index."),
    ] = True,
    search_term: Annotated[
        str | None,
        Query(description="Search term to filter roms."),
    ] = None,
    platform_id: Annotated[
        int | None,
        Query(description="Platform internal id.", ge=1),
    ] = None,
    collection_id: Annotated[
        int | None,
        Query(description="Collection internal id.", ge=1),
    ] = None,
    virtual_collection_id: Annotated[
        str | None,
        Query(description="Virtual collection internal id."),
    ] = None,
    smart_collection_id: Annotated[
        int | None,
        Query(description="Smart collection internal id.", ge=1),
    ] = None,
    matched: Annotated[
        bool | None,
        Query(description="Whether the rom matched a metadata source."),
    ] = None,
    favorite: Annotated[
        bool | None,
        Query(description="Whether the rom is marked as favorite."),
    ] = None,
    duplicate: Annotated[
        bool | None,
        Query(description="Whether the rom is marked as duplicate."),
    ] = None,
    playable: Annotated[
        bool | None,
        Query(description="Whether the rom is playable from the browser."),
    ] = None,
    missing: Annotated[
        bool | None,
        Query(description="Whether the rom is missing from the filesystem."),
    ] = None,
    has_ra: Annotated[
        bool | None,
        Query(description="Whether the rom has RetroAchievements data."),
    ] = None,
    verified: Annotated[
        bool | None,
        Query(
            description="Whether the rom is verified by Hasheous from the filesystem."
        ),
    ] = None,
    group_by_meta_id: Annotated[
        bool,
        Query(
            description="Whether to group roms by metadata ID (IGDB / Moby / ScreenScraper / RetroAchievements / LaunchBox)."
        ),
    ] = False,
    selected_genre: Annotated[
        str | None,
        Query(description="Associated genre."),
    ] = None,
    selected_franchise: Annotated[
        str | None,
        Query(description="Associated franchise."),
    ] = None,
    selected_collection: Annotated[
        str | None,
        Query(description="Associated collection."),
    ] = None,
    selected_company: Annotated[
        str | None,
        Query(description="Associated company."),
    ] = None,
    selected_age_rating: Annotated[
        str | None,
        Query(description="Associated age rating."),
    ] = None,
    selected_status: Annotated[
        str | None,
        Query(description="Game status, set by the current user."),
    ] = None,
    selected_region: Annotated[
        str | None,
        Query(description="Associated region tag."),
    ] = None,
    selected_language: Annotated[
        str | None,
        Query(description="Associated language tag."),
    ] = None,
    order_by: Annotated[
        str,
        Query(description="Field to order results by."),
    ] = "name",
    order_dir: Annotated[
        str,
        Query(description="Order direction, either 'asc' or 'desc'."),
    ] = "asc",
) -> CustomLimitOffsetPage[SimpleRomSchema]:
    """Retrieve roms."""

    # Get the base roms query
    query, order_by_attr = db_rom_handler.get_roms_query(
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
        smart_collection_id=smart_collection_id,
        search_term=search_term,
        matched=matched,
        favorite=favorite,
        duplicate=duplicate,
        playable=playable,
        has_ra=has_ra,
        missing=missing,
        verified=verified,
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
    char_index_dict = {}
    if with_char_index:
        char_index = db_rom_handler.with_char_index(
            query=query, order_by_attr=order_by_attr
        )
        char_index_dict = {char: index for (char, index) in char_index}

    # Get all ROM IDs in order for the additional data
    with sync_session.begin() as session:
        rom_id_index = session.scalars(query.with_only_columns(Rom.id)).all()  # type: ignore

        return paginate(
            session,
            query,
            transformer=lambda items: [
                SimpleRomSchema.from_orm_with_request(i, request) for i in items
            ],
            additional_data={
                "char_index": char_index_dict,
                "rom_id_index": rom_id_index,
            },
        )


@protected_route(
    router.get,
    "/download",
    [Scope.ROMS_READ],
)
async def download_roms(
    request: Request,
    rom_ids: Annotated[
        str,
        Query(
            description="Comma-separated list of ROM IDs to download as a zip file.",
        ),
    ],
    filename: Annotated[
        str | None,
        Query(
            description="Name for the zip file (optional).",
        ),
    ] = None,
):
    """Download a list of roms as a zip file."""

    current_username = (
        request.user.username if request.user.is_authenticated else "unknown"
    )

    if not rom_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ROM IDs provided",
        )

    # Parse comma-separated string into list of integers
    try:
        rom_id_list = [int(id.strip()) for id in rom_ids.split(",") if id.strip()]
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ROM ID format. Must be comma-separated integers.",
        ) from e

    if not rom_id_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid ROM IDs provided",
        )

    rom_objects = db_rom_handler.get_roms_by_ids(rom_id_list)

    if not rom_objects:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ROMs found with the provided IDs",
        )

    # Check if all requested ROMs were found
    found_ids = {rom.id for rom in rom_objects}
    missing_ids = set(rom_id_list) - found_ids
    if missing_ids:
        log.warning(
            f"User {hl(current_username, color=BLUE)} requested ROMs with IDs {missing_ids} that were not found"
        )

    log.info(
        f"User {hl(current_username, color=BLUE)} is downloading {len(rom_objects)} ROMs as zip"
    )

    content_lines = []
    for rom in rom_objects:
        rom_files = sorted(rom.files, key=lambda x: x.file_name)
        for file in rom_files:
            content_lines.append(
                ZipContentLine(
                    crc32=None,  # The CRC hash stored for compressed files is for the uncompressed content
                    size_bytes=file.file_size_bytes,
                    encoded_location=quote(f"/library/{file.full_path}"),
                    filename=file.full_path,
                )
            )

    if filename:
        file_name = sanitize_filename(filename)
    else:
        base64_content = b64encode(
            ("\n".join([str(line) for line in content_lines])).encode()
        )
        file_name = f"{len(rom_objects)} ROMs ({crc32_to_hex(binascii.crc32(base64_content))}).zip"

    return ZipResponse(
        content_lines=content_lines,
        filename=quote(file_name),
    )


@protected_route(
    router.get,
    "/{id}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def get_rom(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> DetailedRomSchema:
    """Retrieve a rom by ID."""

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    return DetailedRomSchema.from_orm_with_request(rom, request)


@protected_route(
    router.head,
    "/{id}/content/{file_name}",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def head_rom_content(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_name: Annotated[str, PathVar(description="File name to download")],
    file_ids: Annotated[
        str | None,
        Query(
            description="Comma-separated list of file ids to download for multi-part roms."
        ),
    ] = None,
):
    """Retrieve head information for a rom file download."""

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    files = list(db_rom_handler.get_rom_files(rom.id))
    if file_ids:
        file_id_values = {int(f.strip()) for f in file_ids.split(",") if f.strip()}
        files = [f for f in files if f.id in file_id_values]
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
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_rom_content(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    file_name: Annotated[str, PathVar(description="Zip file output name")],
    file_ids: Annotated[
        str | None,
        Query(
            description="Comma-separated list of file ids to download for multi-part roms."
        ),
    ] = None,
):
    """Download a rom.

    This endpoint serves the content of the requested rom, as:
    - A single file for single file roms.
    - A zipped file for multi-part roms, including a .m3u file if applicable.
    """

    current_username = (
        request.user.username if request.user.is_authenticated else "unknown"
    )
    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    # https://muos.dev/help/addcontent#what-about-multi-disc-content
    hidden_folder = safe_str_to_bool(request.query_params.get("hidden_folder", ""))

    files = list(db_rom_handler.get_rom_files(rom.id))
    if file_ids:
        file_id_values = {int(f.strip()) for f in file_ids.split(",") if f.strip()}
        files = [f for f in files if f.id in file_id_values]
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
                            filename=file.file_name_for_download(hidden_folder),
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
                        [f.file_name_for_download(hidden_folder) for f in files]
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

    content_lines = [
        ZipContentLine(
            crc32=None,  # The CRC hash stored for compressed files is for the uncompressed content
            size_bytes=f.file_size_bytes,
            encoded_location=quote(f"/library/{f.full_path}"),
            filename=f.file_name_for_download(hidden_folder),
        )
        for f in files
    ]

    if not rom.has_m3u_file():
        m3u_encoded_content = "\n".join(
            [f.file_name_for_download(hidden_folder) for f in files]
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


@protected_route(
    router.put,
    "/{id}",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_rom(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    artwork: Annotated[
        UploadFile | None,
        File(description="Custom artwork to set as cover."),
    ] = None,
    remove_cover: Annotated[
        bool,
        Query(description="Whether to remove the cover image for this rom."),
    ] = False,
    unmatch_metadata: Annotated[
        bool,
        Query(description="Whether to remove the metadata matches for this game."),
    ] = False,
) -> DetailedRomSchema:
    """Update a rom."""
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
                "launchbox_id": None,
                "hasheous_id": None,
                "tgdb_id": None,
                "flashpoint_id": None,
                "hltb_id": None,
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
                "launchbox_metadata": {},
                "hasheous_metadata": {},
                "flashpoint_metadata": {},
                "hltb_metadata": {},
                "revision": "",
            },
        )

        rom = db_rom_handler.get_rom(id)
        if not rom:
            raise RomNotFoundInDatabaseException(id)

        return DetailedRomSchema.from_orm_with_request(rom, request)

    cleaned_data: dict[str, Any] = {
        "igdb_id": (
            safe_int_or_none(data["igdb_id"]) if "igdb_id" in data else rom.igdb_id
        ),
        "sgdb_id": (
            safe_int_or_none(data["sgdb_id"]) if "sgdb_id" in data else rom.sgdb_id
        ),
        "moby_id": (
            safe_int_or_none(data["moby_id"]) if "moby_id" in data else rom.moby_id
        ),
        "ss_id": safe_int_or_none(data["ss_id"]) if "ss_id" in data else rom.ss_id,
        "ra_id": safe_int_or_none(data["ra_id"]) if "ra_id" in data else rom.ra_id,
        "launchbox_id": (
            safe_int_or_none(data["launchbox_id"])
            if "launchbox_id" in data
            else rom.launchbox_id
        ),
        "hasheous_id": (
            safe_int_or_none(data["hasheous_id"])
            if "hasheous_id" in data
            else rom.hasheous_id
        ),
        "tgdb_id": (
            safe_int_or_none(data["tgdb_id"]) if "tgdb_id" in data else rom.tgdb_id
        ),
        "flashpoint_id": (
            data["flashpoint_id"] if "flashpoint_id" in data else rom.flashpoint_id
        ),
        "hltb_id": (
            safe_int_or_none(data["hltb_id"]) if "hltb_id" in data else rom.hltb_id
        ),
    }

    # Add raw metadata parsing
    raw_igdb_metadata = parse_raw_metadata(data, "raw_igdb_metadata")
    raw_moby_metadata = parse_raw_metadata(data, "raw_moby_metadata")
    raw_ss_metadata = parse_raw_metadata(data, "raw_ss_metadata")
    raw_launchbox_metadata = parse_raw_metadata(data, "raw_launchbox_metadata")
    raw_hasheous_metadata = parse_raw_metadata(data, "raw_hasheous_metadata")
    raw_flashpoint_metadata = parse_raw_metadata(data, "raw_flashpoint_metadata")
    raw_hltb_metadata = parse_raw_metadata(data, "raw_hltb_metadata")

    if cleaned_data["igdb_id"] and raw_igdb_metadata is not None:
        cleaned_data["igdb_metadata"] = raw_igdb_metadata
    if cleaned_data["moby_id"] and raw_moby_metadata is not None:
        cleaned_data["moby_metadata"] = raw_moby_metadata
    if cleaned_data["ss_id"] and raw_ss_metadata is not None:
        cleaned_data["ss_metadata"] = raw_ss_metadata
    if cleaned_data["launchbox_id"] and raw_launchbox_metadata is not None:
        cleaned_data["launchbox_metadata"] = raw_launchbox_metadata
    if cleaned_data["hasheous_id"] and raw_hasheous_metadata is not None:
        cleaned_data["hasheous_metadata"] = raw_hasheous_metadata
    if cleaned_data["flashpoint_id"] and raw_flashpoint_metadata is not None:
        cleaned_data["flashpoint_metadata"] = raw_flashpoint_metadata
    if cleaned_data["hltb_id"] and raw_hltb_metadata is not None:
        cleaned_data["hltb_metadata"] = raw_hltb_metadata

    # Fetch metadata from external sources
    if (
        cleaned_data["flashpoint_id"]
        and cleaned_data["flashpoint_id"] != rom.flashpoint_id
    ):
        flashpoint_rom = await meta_flashpoint_handler.get_rom_by_id(
            cleaned_data["flashpoint_id"]
        )
        cleaned_data.update(flashpoint_rom)
    elif rom.flashpoint_id and not cleaned_data["flashpoint_id"]:
        cleaned_data.update({"flashpoint_id": None, "flashpoint_metadata": {}})

    if (
        cleaned_data["launchbox_id"]
        and int(cleaned_data["launchbox_id"]) != rom.launchbox_id
    ):
        launchbox_rom = await meta_launchbox_handler.get_rom_by_id(
            cleaned_data["launchbox_id"]
        )
        cleaned_data.update(launchbox_rom)
    elif rom.launchbox_id and not cleaned_data["launchbox_id"]:
        cleaned_data.update({"launchbox_id": None, "launchbox_metadata": {}})

    if cleaned_data["ra_id"] and int(cleaned_data["ra_id"]) != rom.ra_id:
        ra_rom = await meta_ra_handler.get_rom_by_id(rom, ra_id=cleaned_data["ra_id"])
        cleaned_data.update(ra_rom)
    elif rom.ra_id and not cleaned_data["ra_id"]:
        cleaned_data.update({"ra_id": None, "ra_metadata": {}})

    if cleaned_data["moby_id"] and int(cleaned_data["moby_id"]) != rom.moby_id:
        moby_rom = await meta_moby_handler.get_rom_by_id(
            int(cleaned_data.get("moby_id", ""))
        )
        cleaned_data.update(moby_rom)
    elif rom.moby_id and not cleaned_data["moby_id"]:
        cleaned_data.update({"moby_id": None, "moby_metadata": {}})

    if cleaned_data["ss_id"] and int(cleaned_data["ss_id"]) != rom.ss_id:
        ss_rom = await meta_ss_handler.get_rom_by_id(rom, cleaned_data["ss_id"])
        cleaned_data.update(ss_rom)
    elif rom.ss_id and not cleaned_data["ss_id"]:
        cleaned_data.update({"ss_id": None, "ss_metadata": {}})

    if cleaned_data["igdb_id"] and int(cleaned_data["igdb_id"]) != rom.igdb_id:
        igdb_rom = await meta_igdb_handler.get_rom_by_id(cleaned_data["igdb_id"])
        cleaned_data.update(igdb_rom)
    elif rom.igdb_id and not cleaned_data["igdb_id"]:
        cleaned_data.update({"igdb_id": None, "igdb_metadata": {}})

    if cleaned_data.get("url_screenshots", []):
        path_screenshots = await fs_resource_handler.get_rom_screenshots(
            rom=rom,
            overwrite=True,
            url_screenshots=cleaned_data.get("url_screenshots", []),
        )
        cleaned_data.update(
            {"path_screenshots": path_screenshots, "url_screenshots": []}
        )

    cleaned_data.update(
        {
            "name": data.get("name", rom.name),
            "summary": data.get("summary", rom.summary),
        }
    )

    new_fs_name = str(data.get("fs_name") or rom.fs_name)
    new_fs_name = sanitize_filename(new_fs_name)
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
        cleaned_data.update(await fs_resource_handler.remove_cover(rom))
        cleaned_data.update({"url_cover": ""})
    else:
        if artwork is not None and artwork.filename is not None:
            file_ext = artwork.filename.split(".")[-1]
            artwork_content = BytesIO(await artwork.read())
            (
                path_cover_l,
                path_cover_s,
            ) = await fs_resource_handler.store_artwork(rom, artwork_content, file_ext)

            cleaned_data.update(
                {
                    "url_cover": "",
                    "path_cover_s": path_cover_s,
                    "path_cover_l": path_cover_l,
                }
            )
        else:
            url_cover = data.get("url_cover", rom.url_cover)
            if url_cover != rom.url_cover or not fs_resource_handler.cover_exists(
                rom, CoverSize.BIG
            ):
                path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
                    entity=rom,
                    overwrite=True,
                    url_cover=str(url_cover),
                )
                cleaned_data.update(
                    {
                        "url_cover": url_cover,
                        "path_cover_s": path_cover_s,
                        "path_cover_l": path_cover_l,
                    }
                )
            else:
                cleaned_data.update({"url_cover": rom.url_cover})

    url_manual = data.get("url_manual", rom.url_manual)
    if url_manual != rom.url_manual or not fs_resource_handler.manual_exists(rom):
        path_manual = await fs_resource_handler.get_manual(
            rom=rom,
            overwrite=True,
            url_manual=url_manual,
        )
        cleaned_data.update(
            {
                "url_manual": url_manual,
                "path_manual": path_manual,
            }
        )
    else:
        cleaned_data.update({"url_manual": rom.url_manual})

    # Handle RetroAchievements badges when the ID has changed
    if cleaned_data["ra_id"] and int(cleaned_data["ra_id"]) != rom.ra_id:
        for ach in cleaned_data.get("ra_metadata", {}).get("achievements", []):
            # Store both normal and locked version
            badge_url_lock = ach.get("badge_url_lock", None)
            badge_path_lock = ach.get("badge_path_lock", None)
            if badge_url_lock and badge_path_lock:
                await fs_resource_handler.store_ra_badge(
                    badge_url_lock, badge_path_lock
                )
            badge_url = ach.get("badge_url", None)
            badge_path = ach.get("badge_path", None)
            if badge_url and badge_path:
                await fs_resource_handler.store_ra_badge(badge_url, badge_path)

    # Handle special media files from Screenscraper when the ID has changed
    if cleaned_data["ss_id"] and int(cleaned_data["ss_id"]) != rom.ss_id:
        preferred_media_types = get_preferred_media_types()
        for media_type in preferred_media_types:
            if cleaned_data.get("ss_metadata", {}).get(f"{media_type.value}_path"):
                await fs_resource_handler.store_media_file(
                    cleaned_data["ss_metadata"][f"{media_type.value}_url"],
                    cleaned_data["ss_metadata"][f"{media_type.value}_path"],
                )

    log.debug(
        f"Updating {hl(cleaned_data.get('name', ''), color=BLUE)} [{hl(cleaned_data.get('fs_name', ''))}] with data {cleaned_data}"
    )

    db_rom_handler.update_rom(id, cleaned_data)

    # Rename the file/folder if the name has changed
    should_update_fs = new_fs_name != rom.fs_name
    if should_update_fs:
        try:
            await fs_rom_handler.rename_fs_rom(
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


@protected_route(
    router.post,
    "/{id}/manuals",
    [Scope.ROMS_WRITE],
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def add_rom_manuals(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    filename: Annotated[
        str,
        Header(
            description="The name of the file being uploaded.",
            alias="x-upload-filename",
        ),
    ],
) -> Response:
    """Upload manuals for a rom."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    manuals_path = f"{rom.fs_resources_path}/manual"
    file_location = fs_resource_handler.validate_path(f"{manuals_path}/{rom.id}.pdf")
    log.info(f"Uploading manual to {hl(str(file_location))}")

    await fs_resource_handler.make_directory(manuals_path)

    parser = StreamingFormDataParser(headers=request.headers)
    parser.register("x-upload-platform", NullTarget())
    parser.register(filename, FileTarget(str(file_location)))

    def cleanup_partial_file():
        if file_location.exists():
            file_location.unlink()

    try:
        async for chunk in request.stream():
            parser.data_received(chunk)

        db_rom_handler.update_rom(
            id,
            {
                "path_manual": f"{manuals_path}/{rom.id}.pdf",
            },
        )
    except ClientDisconnect:
        log.error("Client disconnected during upload")
        cleanup_partial_file()
    except Exception as exc:
        log.error("Error uploading files", exc_info=exc)
        cleanup_partial_file()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error uploading the manual",
        ) from exc

    return Response()


@protected_route(
    router.delete,
    "/{id}/manuals",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_manuals(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> Response:
    """Delete manuals for a rom."""

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if not fs_resource_handler.manual_exists(rom):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No manual found for this ROM",
        )

    try:
        await fs_resource_handler.remove_manual(rom)
        db_rom_handler.update_rom(
            id,
            {
                "path_manual": "",
                "url_manual": "",
            },
        )

        log.info(
            f"Deleted manual for {hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
        )
    except FileNotFoundError:
        log.warning(
            f"Manual file not found for {hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]"
        )
        # Still update the database even if file doesn't exist
        db_rom_handler.update_rom(
            id,
            {
                "path_manual": "",
                "url_manual": "",
            },
        )
    except Exception as exc:
        log.error(
            f"Error deleting manual for {hl(rom.name or 'ROM', color=BLUE)} [{hl(rom.fs_name)}]",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error deleting the manual",
        ) from exc

    return Response()


@protected_route(
    router.post,
    "/delete",
    [Scope.ROMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_roms(
    request: Request,
    roms: Annotated[
        list[int],
        Body(
            description="List of rom ids to delete from database.",
            embed=True,
        ),
    ],
    delete_from_fs: Annotated[
        list[int],
        Body(
            description="List of rom ids to delete from filesystem.",
            default_factory=list,
            embed=True,
        ),
    ],
) -> BulkOperationResponse:
    """Delete roms."""

    successful_items = 0
    failed_items = 0
    errors = []

    for id in roms:
        rom = db_rom_handler.get_rom(id)

        if not rom:
            failed_items += 1
            errors.append(f"ROM with ID {id} not found")
            continue

        try:
            log.info(
                f"Deleting {hl(str(rom.name or 'ROM'), color=BLUE)} [{hl(rom.fs_name)}] from database"
            )
            db_rom_handler.delete_rom(id)

            try:
                await fs_resource_handler.remove_directory(rom.fs_resources_path)
            except FileNotFoundError:
                log.warning(
                    f"Couldn't find resources to delete for {hl(str(rom.name or 'ROM'), color=BLUE)}"
                )

            if id in delete_from_fs:
                log.info(f"Deleting {hl(rom.fs_name)} from filesystem")
                try:
                    file_path = f"{rom.fs_path}/{rom.fs_name}"
                    await fs_rom_handler.remove_file(file_path=file_path)
                except FileNotFoundError:
                    error = f"Rom file {hl(rom.fs_name)} not found for platform {hl(rom.platform_display_name, color=BLUE)}[{hl(rom.platform_slug)}]"
                    log.error(error)
                    errors.append(error)
                    failed_items += 1
                    continue

            successful_items += 1
        except Exception as e:
            failed_items += 1
            errors.append(f"Failed to delete ROM {id}: {str(e)}")

    return {
        "successful_items": successful_items,
        "failed_items": failed_items,
        "errors": errors,
    }


@protected_route(
    router.put,
    "/{id}/props",
    [Scope.ROMS_USER_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_rom_user(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    update_last_played: Annotated[
        bool,
        Body(description="Whether to update the last played date."),
    ] = False,
    remove_last_played: Annotated[
        bool,
        Body(description="Whether to remove the last played date."),
    ] = False,
) -> RomUserSchema:
    """Update rom data associated to the current user."""

    # TODO: Migrate to native FastAPI body parsing.
    data = await request.json()
    rom_user_data = data.get("data", {})

    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    db_rom_user = db_rom_handler.get_rom_user(
        id, request.user.id
    ) or db_rom_handler.add_rom_user(id, request.user.id)

    fields_to_update = [
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

    if update_last_played:
        cleaned_data.update({"last_played": datetime.now(timezone.utc)})
    elif remove_last_played:
        cleaned_data.update({"last_played": None})

    rom_user = db_rom_handler.update_rom_user(db_rom_user.id, cleaned_data)

    return RomUserSchema.model_validate(rom_user)


@protected_route(
    router.get,
    "files/{id}",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_romfile(
    request: Request,
    id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
) -> RomFileSchema:
    """Retrieve a rom file by ID."""

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
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_romfile_content(
    request: Request,
    id: Annotated[int, PathVar(description="Rom file internal id.", ge=1)],
    file_name: Annotated[str, PathVar(description="File name to download")],
):
    """Download a rom file."""

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
        rom_path = fs_rom_handler.validate_path(file.full_path)
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


DEFAULT_PUBLIC_ONLY = Query(False, description="Only return public notes")
DEFAULT_SEARCH = Query(None, description="Search notes by title or content")
DEFAULT_TAGS = Query(None, description="Filter by tags")


@protected_route(
    router.get,
    "/{id}/notes",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_rom_notes(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    public_only: bool = DEFAULT_PUBLIC_ONLY,
    search: str = DEFAULT_SEARCH,
    tags: list[str] = DEFAULT_TAGS,
) -> list[UserNoteSchema]:
    """Get all notes for a ROM."""
    from handler.database import db_rom_handler

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    if tags is None:
        tags = []

    notes = db_rom_handler.get_rom_notes(
        rom_id=id,
        user_id=request.user.id,
        public_only=public_only,
        search=search,
        tags=tags,
    )

    return [UserNoteSchema.model_validate(note) for note in notes]


@protected_route(
    router.post,
    "/{id}/notes",
    [Scope.ROMS_USER_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def create_rom_note(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    note_data: Annotated[dict, Body()],
) -> UserNoteSchema:
    """Create a new note for a ROM."""
    from handler.database import db_rom_handler

    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    note = db_rom_handler.create_rom_note(
        rom_id=id,
        user_id=request.user.id,
        title=note_data["title"],
        content=note_data.get("content", ""),
        is_public=note_data.get("is_public", False),
        tags=note_data.get("tags", []),
    )

    # Add username to the note data
    note["username"] = request.user.username
    return UserNoteSchema.model_validate(note)


@protected_route(
    router.put,
    "/{id}/notes/{note_id}",
    [Scope.ROMS_USER_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_rom_note(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    note_id: Annotated[int, PathVar(description="Note id.", ge=1)],
    note_data: Annotated[dict, Body()],
) -> UserNoteSchema:
    """Update a ROM note."""
    from handler.database import db_rom_handler

    note = db_rom_handler.update_rom_note(
        note_id=note_id,
        user_id=request.user.id,
        **{
            k: v
            for k, v in note_data.items()
            if k in ["title", "content", "is_public", "tags"]
        },
    )

    if not note:
        raise HTTPException(
            status_code=404, detail="Note not found or not owned by user"
        )

    # Add username to the note data
    note["username"] = request.user.username
    return UserNoteSchema.model_validate(note)


@protected_route(
    router.delete,
    "/{id}/notes/{note_id}",
    [Scope.ROMS_USER_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_rom_note(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    note_id: Annotated[int, PathVar(description="Note id.", ge=1)],
) -> dict:
    """Delete a ROM note."""
    from handler.database import db_rom_handler

    success = db_rom_handler.delete_rom_note(note_id=note_id, user_id=request.user.id)

    if not success:
        raise HTTPException(
            status_code=404, detail="Note not found or not owned by user"
        )

    return {"message": "Note deleted successfully"}
