import binascii
import json
from base64 import b64encode
from datetime import datetime, timezone
from io import BytesIO
from stat import S_IFREG
from typing import Annotated, Any
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pydash
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
    RomFiltersDict,
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
from models.rom import Rom, RomNote
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
    filter_values: RomFiltersDict
    __params_type__ = CustomLimitOffsetParams


@protected_route(router.get, "", [Scope.ROMS_READ])
def get_roms(
    request: Request,
    with_char_index: Annotated[
        bool,
        Query(description="Whether to get the char index."),
    ] = True,
    with_filter_values: Annotated[
        bool, Query(description="Whether to return filter values.")
    ] = True,
    search_term: Annotated[
        str | None,
        Query(description="Search term to filter roms."),
    ] = None,
    platform_ids: Annotated[
        list[int] | None,
        Query(
            description=(
                "Platform internal ids. Multiple values are allowed by repeating the"
                " parameter, and results that match any of the values will be returned."
            ),
        ),
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
        Query(description="Whether the rom matched at least one metadata source."),
    ] = None,
    favorite: Annotated[
        bool | None,
        Query(description="Whether the rom is marked as favorite."),
    ] = None,
    duplicate: Annotated[
        bool | None,
        Query(description="Whether the rom is marked as duplicate."),
    ] = None,
    last_played: Annotated[
        bool | None,
        Query(
            description="Whether the rom has a last played value for the current user."
        ),
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
        Query(description="Whether the rom is verified by Hasheous."),
    ] = None,
    group_by_meta_id: Annotated[
        bool,
        Query(
            description="Whether to group roms by metadata ID (IGDB / Moby / ScreenScraper / RetroAchievements / LaunchBox)."
        ),
    ] = False,
    genres: Annotated[
        list[str] | None,
        Query(
            description=(
                "Associated genre. Multiple values are allowed by repeating the"
                " parameter, and results that match any of the values will be returned."
            ),
        ),
    ] = None,
    franchises: Annotated[
        list[str] | None,
        Query(
            description=(
                "Associated franchise. Multiple values are allowed by repeating"
                " the parameter, and results that match any of the values will be returned."
            ),
        ),
    ] = None,
    collections: Annotated[
        list[str] | None,
        Query(
            description=(
                "Associated collection. Multiple values are allowed by repeating"
                " the parameter, and results that match any of the values will be returned."
            ),
        ),
    ] = None,
    companies: Annotated[
        list[str] | None,
        Query(
            description=(
                "Associated company. Multiple values are allowed by repeating"
                " the parameter, and results that match any of the values will be returned."
            ),
        ),
    ] = None,
    age_ratings: Annotated[
        list[str] | None,
        Query(
            description=(
                "Associated age rating. Multiple values are allowed by repeating"
                " the parameter, and results that match any of the values will be returned."
            ),
        ),
    ] = None,
    statuses: Annotated[
        list[str] | None,
        Query(
            description=(
                "Game status, set by the current user. Multiple values are allowed by repeating"
                " the parameter, and results that match any of the values will be returned."
            ),
        ),
    ] = None,
    regions: Annotated[
        list[str] | None,
        Query(
            description=(
                "Associated region tag. Multiple values are allowed by repeating"
                " the parameter, and results that match any of the values will be returned."
            ),
        ),
    ] = None,
    languages: Annotated[
        list[str] | None,
        Query(
            description=(
                "Associated language tag. Multiple values are allowed by repeating"
                " the parameter, and results that match any of the values will be returned."
            ),
        ),
    ] = None,
    player_counts: Annotated[
        list[str] | None,
        Query(
            description=(
                "Associated player count. Multiple values are allowed by repeating"
                " the parameter, and results that match any of the values will be returned."
            ),
        ),
    ] = None,
    # Logic operators for multi-value filters
    genres_logic: Annotated[
        str,
        Query(
            description="Logic operator for genres filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    franchises_logic: Annotated[
        str,
        Query(
            description="Logic operator for franchises filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    collections_logic: Annotated[
        str,
        Query(
            description="Logic operator for collections filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    companies_logic: Annotated[
        str,
        Query(
            description="Logic operator for companies filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    age_ratings_logic: Annotated[
        str,
        Query(
            description="Logic operator for age ratings filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    regions_logic: Annotated[
        str,
        Query(
            description="Logic operator for regions filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    languages_logic: Annotated[
        str,
        Query(
            description="Logic operator for languages filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    statuses_logic: Annotated[
        str,
        Query(
            description="Logic operator for statuses filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    player_counts_logic: Annotated[
        str,
        Query(
            description="Logic operator for player counts filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    order_by: Annotated[
        str,
        Query(description="Field to order results by."),
    ] = "name",
    order_dir: Annotated[
        str,
        Query(description="Order direction, either 'asc' or 'desc'."),
    ] = "asc",
    updated_after: Annotated[
        datetime | None,
        Query(
            description="Filter roms updated after this datetime (ISO 8601 format with timezone information)."
        ),
    ] = None,
) -> CustomLimitOffsetPage[SimpleRomSchema]:
    """Retrieve roms."""
    unfiltered_query, order_by_attr = db_rom_handler.get_roms_query(
        user_id=request.user.id,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
    )

    # Filter down the query
    query = db_rom_handler.filter_roms(
        query=unfiltered_query,
        user_id=request.user.id,
        platform_ids=platform_ids,
        collection_id=collection_id,
        virtual_collection_id=virtual_collection_id,
        smart_collection_id=smart_collection_id,
        search_term=search_term,
        matched=matched,
        favorite=favorite,
        duplicate=duplicate,
        last_played=last_played,
        playable=playable,
        has_ra=has_ra,
        missing=missing,
        verified=verified,
        genres=genres,
        franchises=franchises,
        collections=collections,
        companies=companies,
        age_ratings=age_ratings,
        statuses=statuses,
        regions=regions,
        languages=languages,
        player_counts=player_counts,
        # Logic operators
        genres_logic=genres_logic,
        franchises_logic=franchises_logic,
        collections_logic=collections_logic,
        companies_logic=companies_logic,
        age_ratings_logic=age_ratings_logic,
        regions_logic=regions_logic,
        languages_logic=languages_logic,
        statuses_logic=statuses_logic,
        player_counts_logic=player_counts_logic,
        group_by_meta_id=group_by_meta_id,
        updated_after=updated_after,
    )

    # Get the char index for the roms
    char_index_dict = {}
    if with_char_index:
        char_index = db_rom_handler.with_char_index(
            query=query, order_by_attr=order_by_attr
        )
        char_index_dict = {char: index for (char, index) in char_index}

    filter_values = RomFiltersDict(
        genres=[],
        franchises=[],
        collections=[],
        companies=[],
        game_modes=[],
        age_ratings=[],
        player_counts=[],
        regions=[],
        languages=[],
        platforms=[],
    )
    if with_filter_values:
        # We use the unfiltered query so applied filters don't affect the list
        filter_query = db_rom_handler.filter_roms(
            query=unfiltered_query,
            user_id=request.user.id,
            platform_ids=platform_ids,
            collection_id=collection_id,
            virtual_collection_id=virtual_collection_id,
            smart_collection_id=smart_collection_id,
            search_term=search_term,
        )
        query_filters = db_rom_handler.with_filter_values(query=filter_query)
        # trunk-ignore(mypy/typeddict-item)
        filter_values = RomFiltersDict(**query_filters)

    import json

    from sqlalchemy import text

    from config import FRONTEND_RESOURCES_PATH

    def _json(val):
        """Parse JSON strings from raw SQL results."""
        if isinstance(val, str):
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        return val

    with sync_session.begin() as session:
        rom_id_index = session.scalars(query.with_only_columns(Rom.id)).all()  # type: ignore
        total = len(rom_id_index)

        page_offset = int(request.query_params.get("offset", 0))
        page_limit = int(request.query_params.get("limit", 50))
        page_ids = rom_id_index[page_offset : page_offset + page_limit]

        empty_result = {
            "items": [],
            "total": total,
            "limit": page_limit,
            "offset": page_offset,
            "char_index": char_index_dict,
            "rom_id_index": rom_id_index,
            "filter_values": filter_values,
        }
        if not page_ids:
            return empty_result

        placeholders = ",".join([":id_" + str(i) for i in range(len(page_ids))])
        id_params = {f"id_{i}": rid for i, rid in enumerate(page_ids)}

        # Single query for roms + platform + metadata (skips sibling_roms VIEW entirely)
        rows = (
            session.execute(
                text(f"""
            SELECT
                r.id, r.igdb_id, r.sgdb_id, r.moby_id, r.ss_id, r.ra_id,
                r.launchbox_id, r.hasheous_id, r.tgdb_id, r.flashpoint_id,
                r.hltb_id, r.gamelist_id,
                r.fs_name, r.fs_name_no_tags, r.fs_name_no_ext, r.fs_extension,
                r.fs_path, r.fs_size_bytes,
                r.name, r.slug,
                r.ss_metadata, r.gamelist_metadata,
                r.path_cover_s, r.path_cover_l, r.url_cover,
                r.path_manual, r.path_screenshots,
                r.regions, r.languages, r.tags,
                r.missing_from_fs, r.platform_id,
                r.created_at, r.updated_at,
                p.slug AS platform_slug, p.fs_slug AS platform_fs_slug,
                p.custom_name AS platform_custom_name, p.name AS platform_name,
                m.genres, m.franchises, m.collections AS meta_collections,
                m.companies, m.game_modes, m.age_ratings,
                m.player_count, m.first_release_date, m.average_rating
            FROM roms r
            JOIN platforms p ON p.id = r.platform_id
            LEFT JOIN roms_metadata m ON m.rom_id = r.id
            WHERE r.id IN ({placeholders})
        """),
                id_params,
            )
            .mappings()
            .all()
        )

        # Batch-load rom_users and notes (avoids N+1)
        rom_user_rows = (
            session.execute(
                text(f"""
            SELECT rom_id, id, user_id, is_main_sibling, last_played,
                   backlogged, now_playing, hidden, rating, difficulty,
                   completion, status, created_at, updated_at
            FROM rom_user WHERE rom_id IN ({placeholders})
        """),
                id_params,
            )
            .mappings()
            .all()
        )
        rom_users_by_rom: dict = {}
        for ru in rom_user_rows:
            rom_users_by_rom.setdefault(ru["rom_id"], []).append(ru)

        notes_rows = (
            session.execute(
                text(f"""
            SELECT rom_id, user_id, is_public
            FROM rom_notes WHERE rom_id IN ({placeholders})
        """),
                id_params,
            )
            .mappings()
            .all()
        )
        notes_by_rom: dict = {}
        for n in notes_rows:
            notes_by_rom.setdefault(n["rom_id"], []).append(n)

        user_id = request.user.id
        rom_map = {row["id"]: row for row in rows}
        now_str = datetime.now(timezone.utc).isoformat()
        dummy_rom_user = {
            "id": -1,
            "user_id": -1,
            "rom_id": -1,
            "created_at": now_str,
            "updated_at": now_str,
            "last_played": None,
            "is_main_sibling": False,
            "backlogged": False,
            "now_playing": False,
            "hidden": False,
            "rating": 0,
            "difficulty": 0,
            "completion": 0,
            "status": None,
        }

        items = []
        for rid in page_ids:
            row = rom_map.get(rid)
            if not row:
                continue

            # Build dict from row, pop columns that need transformation
            data = dict(row)
            path_cover_s = data.pop("path_cover_s")
            path_cover_l = data.pop("path_cover_l")
            screenshots = _json(data.pop("path_screenshots")) or []
            pname = data.pop("platform_name")
            ts = data["updated_at"]

            # Nest metadata fields
            data["metadatum"] = {
                "rom_id": data["id"],
                "genres": sorted(_json(data.pop("genres")) or []),
                "franchises": sorted(_json(data.pop("franchises")) or []),
                "collections": sorted(_json(data.pop("meta_collections")) or []),
                "companies": sorted(_json(data.pop("companies")) or []),
                "game_modes": sorted(_json(data.pop("game_modes")) or []),
                "age_ratings": sorted(_json(data.pop("age_ratings")) or []),
                "player_count": data.pop("player_count") or "1",
                "first_release_date": data.pop("first_release_date"),
                "average_rating": (
                    float(v) if (v := data.pop("average_rating")) else None
                ),
            }

            # Computed fields (normally on the ORM model)
            data["platform_display_name"] = data["platform_custom_name"] or pname
            data["path_cover_small"] = (
                f"{FRONTEND_RESOURCES_PATH}/{path_cover_s}?ts={ts}"
                if path_cover_s
                else ""
            )
            data["path_cover_large"] = (
                f"{FRONTEND_RESOURCES_PATH}/{path_cover_l}?ts={ts}"
                if path_cover_l
                else ""
            )
            data["full_path"] = f"{data['fs_path']}/{data['fs_name']}"
            data["has_manual"] = bool(data.get("path_manual"))
            data["missing_from_fs"] = bool(data["missing_from_fs"])
            data["merged_screenshots"] = [
                f"{FRONTEND_RESOURCES_PATH}/{s}" for s in screenshots
            ]
            data["url_cover"] = data.get("url_cover") or None
            is_unidentified = not any(
                data.get(k)
                for k in (
                    "igdb_id",
                    "moby_id",
                    "ss_id",
                    "ra_id",
                    "launchbox_id",
                    "hasheous_id",
                    "flashpoint_id",
                    "hltb_id",
                    "gamelist_id",
                )
            )
            data["is_unidentified"] = is_unidentified
            data["is_identified"] = not is_unidentified

            # Parse JSON string columns
            for key in ("regions", "languages", "tags"):
                data[key] = _json(data[key]) or []
            data["ss_metadata"] = _json(data.get("ss_metadata"))
            data["gamelist_metadata"] = _json(data.get("gamelist_metadata"))

            # rom_user + notes from batch queries
            data["rom_user"] = next(
                (
                    dict(ru)
                    for ru in rom_users_by_rom.get(rid, [])
                    if ru["user_id"] == user_id
                ),
                dummy_rom_user,
            )
            data["has_notes"] = any(
                n["is_public"] or n["user_id"] == user_id
                for n in notes_by_rom.get(rid, [])
            )

            items.append(SimpleRomSchema.model_validate(data))

        empty_result["items"] = items
        return empty_result


@protected_route(router.get, "/identifiers", [Scope.ROMS_READ])
def get_rom_identifiers(
    request: Request,
) -> list[int]:
    """Retrieve rom identifiers."""
    db_roms = db_rom_handler.get_roms_scalar(
        user_id=request.user.id,
        only_fields=[Rom.id],
    )

    return [r.id for r in db_roms]


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
    "/by-metadata-provider",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}, status.HTTP_400_BAD_REQUEST: {}},
)
def get_rom_by_metadata_provider(
    request: Request,
    igdb_id: Annotated[int | None, Query(description="IGDB ID to search by")] = None,
    moby_id: Annotated[
        int | None, Query(description="MobyGames ID to search by")
    ] = None,
    ss_id: Annotated[
        int | None, Query(description="ScreenScraper ID to search by")
    ] = None,
    ra_id: Annotated[
        int | None, Query(description="RetroAchievements ID to search by")
    ] = None,
    launchbox_id: Annotated[
        int | None, Query(description="LaunchBox ID to search by")
    ] = None,
    hasheous_id: Annotated[
        int | None, Query(description="Hasheous ID to search by")
    ] = None,
    tgdb_id: Annotated[int | None, Query(description="TGDB ID to search by")] = None,
    flashpoint_id: Annotated[
        str | None, Query(description="Flashpoint ID to search by")
    ] = None,
    hltb_id: Annotated[int | None, Query(description="HLTB ID to search by")] = None,
) -> DetailedRomSchema:
    """Retrieve a rom by metadata ID."""

    if (
        not igdb_id
        and not moby_id
        and not ss_id
        and not ra_id
        and not launchbox_id
        and not hasheous_id
        and not tgdb_id
        and not flashpoint_id
        and not hltb_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one metadata ID must be provided",
        )

    rom = db_rom_handler.get_rom_by_metadata_id(
        igdb_id=igdb_id,
        moby_id=moby_id,
        ss_id=ss_id,
        ra_id=ra_id,
        launchbox_id=launchbox_id,
        hasheous_id=hasheous_id,
        tgdb_id=tgdb_id,
        flashpoint_id=flashpoint_id,
        hltb_id=hltb_id,
    )

    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ROM not found with given metadata IDs",
        )

    return DetailedRomSchema.from_orm_with_request(rom, request)


@protected_route(
    router.get,
    "/by-hash",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}, status.HTTP_400_BAD_REQUEST: {}},
)
def get_rom_by_hash(
    request: Request,
    crc_hash: Annotated[str | None, Query(description="CRC hash value")] = None,
    md5_hash: Annotated[str | None, Query(description="MD5 hash value")] = None,
    sha1_hash: Annotated[str | None, Query(description="SHA1 hash value")] = None,
    ra_hash: Annotated[
        str | None, Query(description="RetroAchievements hash value")
    ] = None,
) -> DetailedRomSchema:
    if not crc_hash and not md5_hash and not sha1_hash and not ra_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one metadata hash value must be provided",
        )

    rom = db_rom_handler.get_rom_by_hash(
        crc_hash=crc_hash,
        md5_hash=md5_hash,
        sha1_hash=sha1_hash,
        ra_hash=ra_hash,
    )

    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ROM or file found with given hash values",
        )

    return DetailedRomSchema.from_orm_with_request(rom, request)


@protected_route(router.get, "/filters", [Scope.ROMS_READ])
async def get_rom_filters(request: Request) -> RomFiltersDict:
    from handler.database import db_rom_handler

    filters = db_rom_handler.get_rom_filters()
    # trunk-ignore(mypy/typeddict-item)
    return RomFiltersDict(**filters)


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

    files = rom.files
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

    files = rom.files
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
                "gamelist_metadata": {},
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
            data["flashpoint_id"] or None
            if "flashpoint_id" in data
            else rom.flashpoint_id
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
    raw_manual_metadata = parse_raw_metadata(data, "raw_manual_metadata")
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
    if raw_manual_metadata is not None:
        cleaned_data["manual_metadata"] = raw_manual_metadata

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

    url_screenshots = cleaned_data.get("url_screenshots", [])
    screenshots_changed = pydash.xor(url_screenshots, rom.url_screenshots or [])
    if url_screenshots:
        path_screenshots = await fs_resource_handler.get_rom_screenshots(
            rom=rom,
            overwrite=bool(screenshots_changed),
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
            path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
                entity=rom,
                overwrite=url_cover != rom.url_cover,
                url_cover=str(url_cover),
            )
            cleaned_data.update(
                {
                    "url_cover": url_cover,
                    "path_cover_s": path_cover_s,
                    "path_cover_l": path_cover_l,
                }
            )

    url_manual = data.get("url_manual", rom.url_manual)
    path_manual = await fs_resource_handler.get_manual(
        rom=rom,
        overwrite=url_manual != rom.url_manual,
        url_manual=str(url_manual) if url_manual else None,
    )
    cleaned_data.update(
        {
            "url_manual": url_manual,
            "path_manual": path_manual,
        }
    )

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
            # Remove old media files if the ss_id is changing
            if rom.ss_metadata and rom.ss_metadata.get(f"{media_type.value}_path"):
                await fs_resource_handler.remove_media_resources_path(
                    rom.platform_id,
                    rom.id,
                    media_type,
                )

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
    "/files/{id}",
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
    router.get,
    "/{id}/notes/identifiers",
    [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def get_rom_note_identifiers(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> list[int]:
    """Get all note identifiers for a ROM."""
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    notes = db_rom_handler.get_rom_notes(
        rom_id=id,
        user_id=request.user.id,
        only_fields=[RomNote.id],
    )

    return [note.id for note in notes]


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
    success = db_rom_handler.delete_rom_note(note_id=note_id, user_id=request.user.id)

    if not success:
        raise HTTPException(
            status_code=404, detail="Note not found or not owned by user"
        )

    return {"message": "Note deleted successfully"}
