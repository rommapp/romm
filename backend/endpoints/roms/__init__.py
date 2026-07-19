import binascii
import json
from base64 import b64encode
from datetime import datetime, timezone
from io import BytesIO
from stat import S_IFREG
from typing import Annotated, Any, Sequence
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pydash
from anyio import Path, open_file
from fastapi import (
    Body,
    Depends,
    File,
    Form,
    HTTPException,
)
from fastapi import Path as PathVar
from fastapi import (
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from fastapi_pagination import resolve_params
from fastapi_pagination.limit_offset import LimitOffsetPage, LimitOffsetParams
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from starlette.responses import FileResponse

from config import (
    DEV_MODE,
    DISABLE_DOWNLOAD_ENDPOINT_AUTH,
    LIBRARY_BASE_PATH,
)
from decorators.auth import protected_route
from endpoints.responses import BulkOperationResponse
from endpoints.responses.rom import (
    DetailedRomSchema,
    RomFiltersDict,
    RomUserSchema,
    SimpleRomSchema,
)
from exceptions.endpoint_exceptions import RomNotFoundInDatabaseException
from exceptions.fs_exceptions import RomAlreadyExistsException
from handler.auth.constants import Scope
from handler.auth.dependencies import (
    assert_can,
    assert_rom_visible,
    get_permissions,
)
from handler.database import db_rom_handler, db_save_handler
from handler.database.base_handler import sync_session
from handler.database.roms_handler import (
    MAX_SIMILAR_ROMS_LIMIT,
    SIMILAR_ROMS_LIMIT,
)
from handler.filesystem import fs_resource_handler, fs_rom_handler
from handler.filesystem.assets_handler import validate_image_upload
from handler.metadata import (
    meta_flashpoint_handler,
    meta_igdb_handler,
    meta_launchbox_handler,
    meta_moby_handler,
    meta_playmatch_handler,
    meta_ra_handler,
    meta_ss_handler,
)
from handler.metadata.launchbox_handler.media import populate_rom_specific_paths
from handler.metadata.ss_handler import add_ss_auth_to_url, get_preferred_media_types
from handler.rom_conversion import promote_single_file_to_folder
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.permission import PermAction, PermEntity
from models.rom import Rom, RomUserStatus, compute_name_sort_key
from utils.background_tasks import fire_and_forget
from utils.database import safe_int, safe_str_to_bool
from utils.filesystem import sanitize_filename
from utils.hashing import crc32_to_hex
from utils.nginx import FileRedirectResponse, ZipContentLine, ZipResponse
from utils.router import APIRouter
from utils.screenshots import continue_playing_screenshot
from utils.validation import ValidationError

from .files import router as files_router
from .manual import router as manual_router
from .notes import router as notes_router
from .patch import router as patch_router
from .screenshot import router as screenshot_router
from .soundtrack import router as soundtrack_router
from .upload import router as upload_router

router = APIRouter(
    prefix="/roms",
    tags=["roms"],
)
router.include_router(upload_router)
router.include_router(files_router)
router.include_router(manual_router)
router.include_router(soundtrack_router)
router.include_router(screenshot_router)
router.include_router(notes_router)
router.include_router(patch_router)


def safe_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None

    return safe_int(value)


def build_unscoped_sidecar_cache_key(
    user_id: int,
    order_by: str,
    order_dir: str,
    group_by_meta_id: bool,
    is_unscoped: bool,
) -> str | None:
    """Cache key for the unscoped library sidecars (char index, filter values,
    rom id index). Returns None for scoped/searched sets, which are computed live.
    The computed values depend on user, ordering and grouping, so all are part
    of the key.
    """
    if not is_unscoped:
        return None

    return (
        f"all:u{user_id}"
        f":o{order_by.lower()}:d{order_dir.lower()}:g{int(group_by_meta_id)}"
    )


class RomUpdateForm(BaseModel):
    igdb_id: str | None = Field(default=None, description="IGDB game ID.")
    sgdb_id: str | None = Field(default=None, description="SteamGridDB game ID.")
    moby_id: str | None = Field(default=None, description="MobyGames game ID.")
    ss_id: str | None = Field(default=None, description="ScreenScraper game ID.")
    ra_id: str | None = Field(default=None, description="RetroAchievements game ID.")
    launchbox_id: str | None = Field(default=None, description="LaunchBox game ID.")
    hasheous_id: str | None = Field(default=None, description="Hasheous game ID.")
    tgdb_id: str | None = Field(default=None, description="TheGamesDB game ID.")
    flashpoint_id: str | None = Field(default=None, description="Flashpoint game ID.")
    hltb_id: str | None = Field(default=None, description="HowLongToBeat game ID.")
    libretro_id: str | None = Field(default=None, description="Libretro thumbnail ID.")
    raw_igdb_metadata: str | None = Field(
        default=None, description="Raw IGDB metadata as JSON string."
    )
    raw_moby_metadata: str | None = Field(
        default=None, description="Raw MobyGames metadata as JSON string."
    )
    raw_ss_metadata: str | None = Field(
        default=None, description="Raw ScreenScraper metadata as JSON string."
    )
    raw_launchbox_metadata: str | None = Field(
        default=None, description="Raw LaunchBox metadata as JSON string."
    )
    raw_hasheous_metadata: str | None = Field(
        default=None, description="Raw Hasheous metadata as JSON string."
    )
    raw_flashpoint_metadata: str | None = Field(
        default=None, description="Raw Flashpoint metadata as JSON string."
    )
    raw_hltb_metadata: str | None = Field(
        default=None, description="Raw HowLongToBeat metadata as JSON string."
    )
    raw_manual_metadata: str | None = Field(
        default=None, description="Raw manual metadata as JSON string."
    )
    name: str | None = None
    name_sort_key: str | None = None
    summary: str | None = None
    fs_name: str | None = None
    url_cover: str | None = None
    url_manual: str | None = None


class RomUserData(BaseModel):
    is_main_sibling: bool | None = Field(
        default=None, description="Whether this rom is the main sibling."
    )
    backlogged: bool | None = Field(
        default=None, description="Whether this rom is in the backlog."
    )
    now_playing: bool | None = Field(
        default=None, description="Whether this rom is currently being played."
    )
    hidden: bool | None = Field(default=None, description="Whether this rom is hidden.")
    rating: int | None = Field(
        default=None, description="User rating for this rom (0-10).", ge=0, le=10
    )
    difficulty: int | None = Field(
        default=None,
        description="User difficulty rating for this rom (0-10).",
        ge=0,
        le=10,
    )
    completion: int | None = Field(
        default=None,
        description="User completion percentage for this rom (0-100).",
        ge=0,
        le=100,
    )
    status: RomUserStatus | None = Field(
        default=None, description="User play status for this rom."
    )


async def parse_rom_update_form(
    request: Request,
    igdb_id: str | None = Form(default=None),
    sgdb_id: str | None = Form(default=None),
    moby_id: str | None = Form(default=None),
    ss_id: str | None = Form(default=None),
    ra_id: str | None = Form(default=None),
    launchbox_id: str | None = Form(default=None),
    hasheous_id: str | None = Form(default=None),
    tgdb_id: str | None = Form(default=None),
    flashpoint_id: str | None = Form(default=None),
    hltb_id: str | None = Form(default=None),
    libretro_id: str | None = Form(default=None),
    raw_igdb_metadata: str | None = Form(default=None),
    raw_moby_metadata: str | None = Form(default=None),
    raw_ss_metadata: str | None = Form(default=None),
    raw_launchbox_metadata: str | None = Form(default=None),
    raw_hasheous_metadata: str | None = Form(default=None),
    raw_flashpoint_metadata: str | None = Form(default=None),
    raw_hltb_metadata: str | None = Form(default=None),
    raw_manual_metadata: str | None = Form(default=None),
    name: str | None = Form(default=None),
    name_sort_key: str | None = Form(default=None),
    summary: str | None = Form(default=None),
    fs_name: str | None = Form(default=None),
    url_cover: str | None = Form(default=None),
    url_manual: str | None = Form(default=None),
) -> RomUpdateForm:
    # Preserve "field was provided" behavior used by update logic.
    form_keys = set((await request.form()).keys())
    field_values = {
        "igdb_id": igdb_id,
        "sgdb_id": sgdb_id,
        "moby_id": moby_id,
        "ss_id": ss_id,
        "ra_id": ra_id,
        "launchbox_id": launchbox_id,
        "hasheous_id": hasheous_id,
        "tgdb_id": tgdb_id,
        "flashpoint_id": flashpoint_id,
        "hltb_id": hltb_id,
        "libretro_id": libretro_id,
        "raw_igdb_metadata": raw_igdb_metadata,
        "raw_moby_metadata": raw_moby_metadata,
        "raw_ss_metadata": raw_ss_metadata,
        "raw_launchbox_metadata": raw_launchbox_metadata,
        "raw_hasheous_metadata": raw_hasheous_metadata,
        "raw_flashpoint_metadata": raw_flashpoint_metadata,
        "raw_hltb_metadata": raw_hltb_metadata,
        "raw_manual_metadata": raw_manual_metadata,
        "name": name,
        "name_sort_key": name_sort_key,
        "summary": summary,
        "fs_name": fs_name,
        "url_cover": url_cover,
        "url_manual": url_manual,
    }

    return RomUpdateForm.model_validate(
        {field: value for field, value in field_values.items() if field in form_keys}
    )


def parse_raw_metadata(form_data: RomUpdateForm, form_key: str) -> dict | None:
    if form_key not in form_data.model_fields_set:
        return None

    raw_json = getattr(form_data, form_key, None)
    if not raw_json or str(raw_json).strip() == "":
        return None

    try:
        return json.loads(str(raw_json))
    except json.JSONDecodeError as e:
        log.warning(f"Invalid JSON for {form_key}: {e}")
        return None


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
    with_rom_id_index: Annotated[
        bool,
        Query(
            description=(
                "Whether to return the full ordered rom id index that backs virtual scroll."
            )
        ),
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
    has_saves: Annotated[
        bool | None,
        Query(description="Whether the rom has saves for the current user."),
    ] = None,
    has_states: Annotated[
        bool | None,
        Query(description="Whether the rom has save states for the current user."),
    ] = None,
    verified: Annotated[
        bool | None,
        Query(description="Whether the rom is verified by Hasheous."),
    ] = None,
    has_soundtrack: Annotated[
        bool | None,
        Query(description="Whether the rom has any soundtrack files."),
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
    metadata_providers: Annotated[
        list[str] | None,
        Query(
            description=(
                "Matched metadata provider (igdb, moby, ss, ra, launchbox, hasheous,"
                " flashpoint, hltb, gamelist, libretro). Multiple values are allowed by"
                " repeating the parameter, and results that match any of the values"
                " will be returned."
            ),
        ),
    ] = None,
    tags: Annotated[
        list[str] | None,
        Query(
            description=(
                "Associated custom tag (parsed from the filename, e.g. Proto, Beta,"
                " Demo). Multiple values are allowed by repeating the parameter, and"
                " results that match any of the values will be returned."
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
    metadata_providers_logic: Annotated[
        str,
        Query(
            description="Logic operator for metadata providers filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    tags_logic: Annotated[
        str,
        Query(
            description="Logic operator for tags filter: 'any' (OR), 'all' (AND) or 'none' (NOT).",
        ),
    ] = "any",
    order_by: Annotated[
        str,
        Query(
            description=(
                "Field to order results by. Leave empty to order by search "
                "relevance when a search term is given on MySQL/MariaDB; other "
                "databases fall back to name."
            ),
        ),
    ] = "",
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
    with_files: Annotated[
        bool,
        Query(description="Whether to include each rom's file entries."),
    ] = False,
) -> CustomLimitOffsetPage[SimpleRomSchema]:
    """Retrieve roms."""
    perms = get_permissions(request)

    unfiltered_query, order_by_attr = db_rom_handler.get_roms_query(
        user_id=request.user.id,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
        search_term=search_term,
    )

    # Filter down the query
    query = db_rom_handler.filter_roms(
        query=unfiltered_query,
        user_id=request.user.id,
        hidden_platform_ids=perms.hidden_platform_ids,
        hidden_rom_ids=perms.hidden_rom_ids,
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
        has_saves=has_saves,
        has_states=has_states,
        missing=missing,
        verified=verified,
        has_soundtrack=has_soundtrack,
        genres=genres,
        franchises=franchises,
        collections=collections,
        companies=companies,
        age_ratings=age_ratings,
        statuses=statuses,
        regions=regions,
        languages=languages,
        player_counts=player_counts,
        metadata_providers=metadata_providers,
        tags=tags,
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
        metadata_providers_logic=metadata_providers_logic,
        tags_logic=tags_logic,
        group_by_meta_id=group_by_meta_id,
        updated_after=updated_after,
        include_file_stats=True,
    )

    # Cache only the fully unscoped library scan; any narrowing parameter makes
    # the result set narrower, so it is computed live. The sidecar cache key
    # encodes only user/order/grouping, not the filters, so every filter applied
    # to `query` below must gate caching here or a narrowed list leaks under the
    # shared "all" key. Bool flags use `is not None` since False is an active
    # filter. Logic operators are omitted: they only matter when their list
    # filter is set, which is already covered.
    is_unscoped = not (
        search_term
        or platform_ids
        or collection_id
        or virtual_collection_id
        or smart_collection_id
        or genres
        or franchises
        or collections
        or companies
        or age_ratings
        or statuses
        or regions
        or languages
        or player_counts
        or metadata_providers
        or tags
        or updated_after
        or matched is not None
        or favorite is not None
        or duplicate is not None
        or last_played is not None
        or playable is not None
        or has_ra is not None
        or has_saves is not None
        or has_states is not None
        or missing is not None
        or verified is not None
        or has_soundtrack is not None
    )

    # Get the char index for the roms
    char_index_dict = {}
    if with_char_index:
        # Switching sort direction/column (or toggling grouping) must not reuse
        # a stale index, or the AlphaStrip highlights the wrong letters.
        char_index_cache_key = build_unscoped_sidecar_cache_key(
            request.user.id, order_by, order_dir, group_by_meta_id, is_unscoped
        )
        char_index = db_rom_handler.with_char_index(
            query=query,
            order_by_attr=order_by_attr,
            order_dir=order_dir.lower(),
            cache_key=char_index_cache_key,
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
        tags=[],
        platforms=[],
    )
    if with_filter_values:
        # We use the unfiltered query so applied filters don't affect the list
        filter_query = db_rom_handler.filter_roms(
            query=unfiltered_query,
            user_id=request.user.id,
            hidden_platform_ids=list(perms.hidden_platform_ids),
            hidden_rom_ids=list(perms.hidden_rom_ids),
            platform_ids=platform_ids,
            collection_id=collection_id,
            virtual_collection_id=virtual_collection_id,
            smart_collection_id=smart_collection_id,
            search_term=search_term,
        )
        cache_key = build_unscoped_sidecar_cache_key(
            request.user.id, order_by, order_dir, group_by_meta_id, is_unscoped
        )
        query_filters = db_rom_handler.with_filter_values(
            query=filter_query,
            cache_key=cache_key,
        )
        # trunk-ignore(mypy/typeddict-item)
        filter_values = RomFiltersDict(**query_filters)

    # The full ordered id list backs virtual scroll, so it's computed over the
    # whole result set. Callers that only need a page (e.g. the home rails) opt
    # out with with_rom_id_index=false and avoid the full-library scan.
    rom_id_index: list[int] = []
    if with_rom_id_index:
        # Memoise the unscoped library scan (same key scheme as the other
        # sidecars); scoped/searched sets stay live.
        rom_id_index_cache_key = build_unscoped_sidecar_cache_key(
            request.user.id, order_by, order_dir, group_by_meta_id, is_unscoped
        )
        rom_id_index = db_rom_handler.get_rom_id_index(
            query=query, cache_key=rom_id_index_cache_key
        )

    # Hydrate the requested page and its additional data
    with sync_session.begin() as session:

        def _transform(items: Sequence[Rom]) -> list[SimpleRomSchema]:
            rom_ids = [i.id for i in items]
            files_by_rom = (
                db_rom_handler.get_files_for_roms(rom_ids, session=session)
                if with_files
                else {}
            )
            siblings_by_rom = db_rom_handler.get_siblings_for_roms(
                rom_ids,
                user_id=request.user.id,
                session=session,
                hidden_platform_ids=list(perms.hidden_platform_ids),
                hidden_rom_ids=list(perms.hidden_rom_ids),
            )

            # Continue-playing rail
            screenshot_by_rom: dict[int, str | None] = {}
            if last_played:
                latest_saves = db_save_handler.get_latest_saves_for_roms(
                    user_id=request.user.id, rom_ids=rom_ids, session=session
                )
                for item in items:
                    screenshot_by_rom[item.id] = continue_playing_screenshot(
                        item, latest_saves.get(item.id)
                    )

            return [
                SimpleRomSchema.from_orm_with_request(
                    db_rom=item,
                    request=request,
                    files=files_by_rom.get(item.id, []),
                    siblings=siblings_by_rom.get(item.id, []),
                    screenshot_path=screenshot_by_rom.get(item.id),
                )
                for item in items
            ]

        params = resolve_params()
        if with_rom_id_index:
            total = len(rom_id_index)
            page_ids = list(rom_id_index[params.offset : params.offset + params.limit])
            if page_ids:
                page_rows = session.scalars(query.where(Rom.id.in_(page_ids))).all()
                rows_by_id = {rom.id: rom for rom in page_rows}
                page_items = [rows_by_id[i] for i in page_ids if i in rows_by_id]
            else:
                page_items = []
        else:
            # Let the database serve the page from the sort index instead of
            # walking the whole primary key to build a full id list.
            page_items = list(
                session.scalars(query.offset(params.offset).limit(params.limit)).all()
            )
            total = db_rom_handler.get_rom_count(query=query, session=session)

        return CustomLimitOffsetPage.create(
            _transform(page_items),
            params,
            total=total,
            char_index=char_index_dict,
            rom_id_index=list(rom_id_index),
            filter_values=filter_values,
        )


@protected_route(router.get, "/identifiers", [Scope.ROMS_READ])
def get_rom_identifiers(
    request: Request,
) -> list[int]:
    """Retrieve rom identifiers."""
    perms = get_permissions(request)
    db_roms = db_rom_handler.get_roms_scalar(
        user_id=request.user.id,
        only_fields=[Rom.id],
        hidden_platform_ids=perms.hidden_platform_ids,
        hidden_rom_ids=perms.hidden_rom_ids,
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
        str | None,
        Query(
            description="Comma-separated list of ROM IDs to download as a zip file.",
        ),
    ] = None,
    platform_id: Annotated[
        int | None,
        Query(description="Download every ROM in this platform as a zip file."),
    ] = None,
    collection_id: Annotated[
        int | None,
        Query(description="Download every ROM in this collection as a zip file."),
    ] = None,
    virtual_collection_id: Annotated[
        str | None,
        Query(
            description="Download every ROM in this virtual collection as a zip file.",
        ),
    ] = None,
    smart_collection_id: Annotated[
        int | None,
        Query(description="Download every ROM in this smart collection as a zip file."),
    ] = None,
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
    perms = get_permissions(request)

    # Resolve the target ROM IDs
    if platform_id or collection_id or virtual_collection_id or smart_collection_id:
        rom_rows = db_rom_handler.get_roms_scalar(
            user_id=request.user.id,
            only_fields=[Rom.id],
            platform_ids=[platform_id] if platform_id else None,
            collection_id=collection_id,
            virtual_collection_id=virtual_collection_id,
            smart_collection_id=smart_collection_id,
            hidden_platform_ids=list(perms.hidden_platform_ids),
            hidden_rom_ids=list(perms.hidden_rom_ids),
        )
        rom_id_list = list(dict.fromkeys(rom.id for rom in rom_rows))
    elif rom_ids:
        # Parse comma-separated string into list of integers
        try:
            rom_id_list = [int(id.strip()) for id in rom_ids.split(",") if id.strip()]
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid ROM ID format. Must be comma-separated integers.",
            ) from e
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ROM IDs or platform/collection selector provided",
        )

    if not rom_id_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ROMs found to download",
        )

    rom_objects = db_rom_handler.get_roms_by_ids(rom_id_list)

    # Drop roms hidden from the caller so they can't be pulled by direct id.
    if request.user.is_authenticated:
        rom_objects = [
            rom for rom in rom_objects if perms.can_see_rom(rom.id, rom.platform_id)
        ]

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

    not_found_detail = "ROM not found with given metadata IDs"
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail
        )

    assert_rom_visible(request, rom, not_found_detail=not_found_detail)

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

    not_found_detail = "No ROM or file found with given hash values"
    if not rom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail
        )

    assert_rom_visible(request, rom, not_found_detail=not_found_detail)

    return DetailedRomSchema.from_orm_with_request(rom, request)


@protected_route(router.get, "/filters", [Scope.ROMS_READ])
async def get_rom_filters(request: Request) -> RomFiltersDict:
    from handler.database import db_rom_handler

    filters = db_rom_handler.get_rom_filters()
    # trunk-ignore(mypy/typeddict-item)
    return RomFiltersDict(**filters)


@protected_route(
    router.get,
    "/{id}/simple",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def get_rom_simple(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> SimpleRomSchema:
    """Retrieve a rom by ID with the lightweight schema — no eager-loaded
    `user_saves` / `user_states` / `user_screenshots` / `user_collections` /
    `all_user_notes` arrays. Designed for the v2 gallery card which only
    needs the indicator flags (`has_notes`, `ra_id`, status, etc.) already
    present on `SimpleRomSchema`. The full `DetailedRomSchema` is only
    fetched on user-driven detail interactions (game details page, quick-
    note dialog open, achievements panel)."""

    rom = db_rom_handler.get_rom_simple(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    return SimpleRomSchema.from_orm_with_request(rom, request)


@protected_route(
    router.get,
    "/{id}/similar",
    [] if DISABLE_DOWNLOAD_ENDPOINT_AUTH else [Scope.ROMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def get_similar_roms(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
    limit: Annotated[
        int,
        Query(
            description="Max number of similar ROMs to return.",
            ge=1,
            le=MAX_SIMILAR_ROMS_LIMIT,
        ),
    ] = SIMILAR_ROMS_LIMIT,
) -> list[SimpleRomSchema]:
    """Return library ROMs similar to the given ROM.

    Similarity is computed from the normalized `RomMetadata` signals
    (franchises, collections, genres, companies, age ratings), so only ROMs
    already in the library are returned. ROMs hidden from the caller are
    excluded."""

    rom = db_rom_handler.get_rom_simple(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    perms = get_permissions(request)
    similar_ids = db_rom_handler.get_similar_rom_ids(
        rom,
        limit=limit,
        hidden_platform_ids=list(perms.hidden_platform_ids),
        hidden_rom_ids=list(perms.hidden_rom_ids),
    )
    if not similar_ids:
        return []

    roms_by_id = {r.id: r for r in db_rom_handler.get_roms_by_ids(similar_ids)}
    ordered = [roms_by_id[i] for i in similar_ids if i in roms_by_id]
    return [SimpleRomSchema.from_orm_with_request(r, request) for r in ordered]


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

    assert_rom_visible(request, rom)

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

    assert_rom_visible(request, rom)

    files = rom.files
    if file_ids:
        file_id_values = {int(f.strip()) for f in file_ids.split(",") if f.strip()}
        files = [f for f in files if f.id in file_id_values]
    files.sort(key=lambda x: x.file_name)

    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No files found for ROM {id}",
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

    assert_rom_visible(request, rom)

    # https://muos.dev/help/addcontent#what-about-multi-disc-content
    hidden_folder = safe_str_to_bool(request.query_params.get("hidden_folder", ""))

    files = rom.files
    if file_ids:
        file_id_values = {int(f.strip()) for f in file_ids.split(",") if f.strip()}
        files = [f for f in files if f.id in file_id_values]
    files.sort(key=lambda x: x.file_name)

    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No files found for ROM {id}",
        )

    log.info(
        f"User {hl(current_username, color=BLUE)} is downloading {hl(rom.fs_name)}"
    )

    # If .cue files are present, only list those in the M3U
    # (avoids invalid entries like raw .bin tracks)
    cue_files = [f for f in files if f.file_extension.lower() == "cue"]
    m3u_files = cue_files if cue_files else files

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
                        [f.file_name_for_download(hidden_folder) for f in m3u_files]
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
            [f.file_name_for_download(hidden_folder) for f in m3u_files]
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
    form_data: Annotated[RomUpdateForm, Depends(parse_rom_update_form)],
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
    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

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
                "libretro_id": None,
                "name": rom.fs_name,
                "name_sort_key": compute_name_sort_key(rom.fs_name),
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

        db_rom_handler.invalidate_filter_values_cache()
        return DetailedRomSchema.from_orm_with_request(rom, request)

    provided_fields = form_data.model_fields_set
    cleaned_data: dict[str, Any] = {
        "igdb_id": (
            safe_int_or_none(form_data.igdb_id)
            if "igdb_id" in provided_fields
            else rom.igdb_id
        ),
        "sgdb_id": (
            safe_int_or_none(form_data.sgdb_id)
            if "sgdb_id" in provided_fields
            else rom.sgdb_id
        ),
        "moby_id": (
            safe_int_or_none(form_data.moby_id)
            if "moby_id" in provided_fields
            else rom.moby_id
        ),
        "ss_id": (
            safe_int_or_none(form_data.ss_id)
            if "ss_id" in provided_fields
            else rom.ss_id
        ),
        "ra_id": (
            safe_int_or_none(form_data.ra_id)
            if "ra_id" in provided_fields
            else rom.ra_id
        ),
        "launchbox_id": (
            safe_int_or_none(form_data.launchbox_id)
            if "launchbox_id" in provided_fields
            else rom.launchbox_id
        ),
        "hasheous_id": (
            safe_int_or_none(form_data.hasheous_id)
            if "hasheous_id" in provided_fields
            else rom.hasheous_id
        ),
        "tgdb_id": (
            safe_int_or_none(form_data.tgdb_id)
            if "tgdb_id" in provided_fields
            else rom.tgdb_id
        ),
        "flashpoint_id": (
            form_data.flashpoint_id or None
            if "flashpoint_id" in provided_fields
            else rom.flashpoint_id
        ),
        "hltb_id": (
            safe_int_or_none(form_data.hltb_id)
            if "hltb_id" in provided_fields
            else rom.hltb_id
        ),
        "libretro_id": (
            form_data.libretro_id or None
            if "libretro_id" in provided_fields
            else rom.libretro_id
        ),
    }

    # Add raw metadata parsing
    raw_igdb_metadata = parse_raw_metadata(form_data, "raw_igdb_metadata")
    raw_moby_metadata = parse_raw_metadata(form_data, "raw_moby_metadata")
    raw_ss_metadata = parse_raw_metadata(form_data, "raw_ss_metadata")
    raw_launchbox_metadata = parse_raw_metadata(form_data, "raw_launchbox_metadata")
    raw_hasheous_metadata = parse_raw_metadata(form_data, "raw_hasheous_metadata")
    raw_flashpoint_metadata = parse_raw_metadata(form_data, "raw_flashpoint_metadata")
    raw_hltb_metadata = parse_raw_metadata(form_data, "raw_hltb_metadata")
    raw_manual_metadata = parse_raw_metadata(form_data, "raw_manual_metadata")
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
        if flashpoint_rom.get("flashpoint_id"):
            cleaned_data.update(flashpoint_rom)
    elif rom.flashpoint_id and not cleaned_data["flashpoint_id"]:
        cleaned_data.update({"flashpoint_id": None, "flashpoint_metadata": {}})

    if (
        cleaned_data["launchbox_id"]
        and int(cleaned_data["launchbox_id"]) != rom.launchbox_id
    ):
        launchbox_rom = await meta_launchbox_handler.get_rom_by_id(
            cleaned_data["launchbox_id"],
            fs_name=rom.fs_name,
            platform_slug=rom.platform_slug,
        )
        if launchbox_rom.get("launchbox_id"):
            metadata = launchbox_rom.get("launchbox_metadata")
            if metadata:
                populate_rom_specific_paths(metadata, rom)
            cleaned_data.update(launchbox_rom)
    elif rom.launchbox_id and not cleaned_data["launchbox_id"]:
        cleaned_data.update({"launchbox_id": None, "launchbox_metadata": {}})

    if cleaned_data["ra_id"] and int(cleaned_data["ra_id"]) != rom.ra_id:
        ra_rom = await meta_ra_handler.get_rom_by_id(rom, ra_id=cleaned_data["ra_id"])
        if ra_rom.get("ra_id"):
            cleaned_data.update(ra_rom)
    elif rom.ra_id and not cleaned_data["ra_id"]:
        cleaned_data.update({"ra_id": None, "ra_metadata": {}})

    if cleaned_data["moby_id"] and int(cleaned_data["moby_id"]) != rom.moby_id:
        moby_rom = await meta_moby_handler.get_rom_by_id(
            int(cleaned_data.get("moby_id", ""))
        )
        if moby_rom.get("moby_id"):
            cleaned_data.update(moby_rom)
    elif rom.moby_id and not cleaned_data["moby_id"]:
        cleaned_data.update({"moby_id": None, "moby_metadata": {}})

    if cleaned_data["ss_id"] and int(cleaned_data["ss_id"]) != rom.ss_id:
        ss_rom = await meta_ss_handler.get_rom_by_id(rom, cleaned_data["ss_id"])
        if ss_rom.get("ss_id"):
            cleaned_data.update(ss_rom)
    elif rom.ss_id and not cleaned_data["ss_id"]:
        cleaned_data.update({"ss_id": None, "ss_metadata": {}})

    if cleaned_data["igdb_id"] and int(cleaned_data["igdb_id"]) != rom.igdb_id:
        igdb_rom = await meta_igdb_handler.get_rom_by_id(rom, cleaned_data["igdb_id"])
        if igdb_rom.get("igdb_id"):
            cleaned_data.update(igdb_rom)
    elif rom.igdb_id and not cleaned_data["igdb_id"]:
        cleaned_data.update({"igdb_id": None, "igdb_metadata": {}})

    url_screenshots = cleaned_data.get("url_screenshots", [])
    screenshots_changed = pydash.xor(url_screenshots, rom.url_screenshots or [])
    if url_screenshots:
        try:
            path_screenshots = await fs_resource_handler.get_rom_screenshots(
                rom=rom,
                overwrite=bool(screenshots_changed),
                url_screenshots=[add_ss_auth_to_url(u) for u in url_screenshots],
            )
            cleaned_data.update(
                {"path_screenshots": path_screenshots, "url_screenshots": []}
            )
        except ValidationError as e:
            log.error(f"Invalid screenshot URL in update_rom: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e)) from e

    name_value = form_data.name if "name" in provided_fields else rom.name
    cleaned_data.update(
        {
            "name": name_value,
            "summary": (
                form_data.summary if "summary" in provided_fields else rom.summary
            ),
        }
    )

    if "name_sort_key" in provided_fields:
        # The edit form always echoes the current key back, so only act when the
        # user actually changed it: a value is a custom override, an empty value
        # reverts to deriving from the (possibly new) name. When unchanged, leave
        # it out so update_rom re-derives only if the stored key isn't custom.
        submitted = (form_data.name_sort_key or "").strip()
        if submitted != (rom.name_sort_key or "").strip():
            cleaned_data["name_sort_key"] = compute_name_sort_key(
                submitted or name_value
            )

    new_fs_name = str(form_data.fs_name or rom.fs_name)
    new_fs_name = sanitize_filename(new_fs_name)
    cleaned_data.update({"fs_name": new_fs_name})

    # Re-parse tags from the filename so region/language/revision/version/tags
    # stay in sync whenever the fs_name changes.
    if new_fs_name != rom.fs_name:
        parsed_tags = fs_rom_handler.parse_tags(new_fs_name)
        cleaned_data.update(
            {
                "regions": parsed_tags.regions,
                "languages": parsed_tags.languages,
                "tags": parsed_tags.other_tags,
                "revision": parsed_tags.revision,
                "version": parsed_tags.version,
            }
        )

    if remove_cover:
        cleaned_data.update(await fs_resource_handler.remove_cover(rom))
        cleaned_data.update({"url_cover": ""})
    else:
        if artwork is not None and artwork.filename is not None:
            file_ext = validate_image_upload(artwork, label="Artwork")
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
            url_cover = (
                form_data.url_cover if "url_cover" in provided_fields else rom.url_cover
            )
            try:
                path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
                    entity=rom,
                    overwrite=url_cover != rom.url_cover,
                    url_cover=add_ss_auth_to_url(url_cover),
                )
                cleaned_data.update(
                    {
                        "url_cover": url_cover,
                        "path_cover_s": path_cover_s,
                        "path_cover_l": path_cover_l,
                    }
                )
            except ValidationError as e:
                log.error(f"Invalid cover URL in update_rom: {str(e)}")
                raise HTTPException(status_code=400, detail=str(e)) from e

    url_manual = (
        form_data.url_manual if "url_manual" in provided_fields else rom.url_manual
    )
    try:
        path_manual = await fs_resource_handler.get_manual(
            rom=rom,
            overwrite=url_manual != rom.url_manual,
            url_manual=add_ss_auth_to_url(url_manual),
        )
        cleaned_data.update(
            {
                "url_manual": url_manual,
                "path_manual": path_manual,
            }
        )
    except ValidationError as e:
        log.error(f"Invalid manual URL in update_rom: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e

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

            media_path = cleaned_data.get("ss_metadata", {}).get(
                f"{media_type.value}_path"
            )
            media_url = cleaned_data.get("ss_metadata", {}).get(
                f"{media_type.value}_url"
            )
            if media_path and media_url:
                await fs_resource_handler.store_media_file(
                    add_ss_auth_to_url(media_url),
                    media_path,
                )

    # Handle local media files from LaunchBox when the ID has changed
    if (
        cleaned_data["launchbox_id"]
        and int(cleaned_data["launchbox_id"]) != rom.launchbox_id
    ):
        preferred_media_types = get_preferred_media_types()

        for media_type in preferred_media_types:
            # Remove old media files if the launchbox_id is changing
            if rom.launchbox_metadata and rom.launchbox_metadata.get(
                f"{media_type.value}_path"
            ):
                await fs_resource_handler.remove_media_resources_path(
                    rom.platform_id,
                    rom.id,
                    media_type,
                )

            media_path = cleaned_data.get("launchbox_metadata", {}).get(
                f"{media_type.value}_path"
            )
            media_url = cleaned_data.get("launchbox_metadata", {}).get(
                f"{media_type.value}_url"
            )
            if media_path and media_url:
                await fs_resource_handler.store_media_file(
                    media_url,
                    media_path,
                )

    log.debug(
        f"Updating {hl(cleaned_data.get('name', ''), color=BLUE)} [{hl(cleaned_data.get('fs_name', ''))}] with data {cleaned_data}"
    )

    try:
        db_rom_handler.update_rom(id, cleaned_data)
    except IntegrityError as exc:
        log.error(f"Failed to update ROM {id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update ROM {id}: {exc}",
        ) from exc

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

    if meta_playmatch_handler.is_manual_match(form_data.model_fields_set):
        fire_and_forget(meta_playmatch_handler.submit_manual_match_suggestion(rom))

    db_rom_handler.invalidate_filter_values_cache()
    return DetailedRomSchema.from_orm_with_request(rom, request)


@protected_route(
    router.post,
    "/{id}/convert-to-folder",
    [Scope.ROMS_WRITE],
    responses={
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_409_CONFLICT: {},
    },
)
async def convert_rom_to_folder(
    request: Request,
    id: Annotated[int, PathVar(description="Rom internal id.", ge=1)],
) -> DetailedRomSchema:
    """Promote a single-file ROM to a folder ROM in place.

    Keeps the same id and all relations; no rescan. A no-op (clean success) if
    the ROM is already folder-based. Returns 409 on a folder-name collision.
    """
    rom = db_rom_handler.get_rom(id)
    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    try:
        rom = await promote_single_file_to_folder(rom)
    except RomAlreadyExistsException as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return DetailedRomSchema.from_orm_with_request(rom, request)


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

    perms = get_permissions(request)
    assert_can(perms, PermEntity.ROMS, PermAction.DELETE)

    successful_items = 0
    failed_items = 0
    errors = []

    for id in roms:
        rom = db_rom_handler.get_rom(id)

        # Hidden roms are masked as not-found rather than reported deletable.
        if not rom or not perms.can_see_rom(rom.id, rom.platform_id):
            failed_items += 1
            errors.append(f"ROM with ID {id} not found")
            continue

        try:
            if id in delete_from_fs:
                log.info(f"Deleting {hl(rom.fs_name)} from filesystem")
                try:
                    rom_path = f"{rom.fs_path}/{rom.fs_name}"
                    full_path = fs_rom_handler.validate_path(rom_path)
                    if full_path.is_dir():
                        await fs_rom_handler.remove_directory(rom_path)
                    else:
                        await fs_rom_handler.remove_file(rom_path)
                        # Clean up empty parent directory if it becomes empty
                        parent = full_path.parent
                        if (
                            parent != fs_rom_handler.base_path
                            and parent.is_dir()
                            and not any(parent.iterdir())
                        ):
                            try:
                                await fs_rom_handler.remove_directory(
                                    str(parent.relative_to(fs_rom_handler.base_path))
                                )
                            except OSError as dir_err:
                                log.warning(
                                    f"Couldn't clean up empty parent directory for {hl(rom.fs_name)}: {dir_err}"
                                )
                except FileNotFoundError:
                    log.warning(
                        f"Rom file {hl(rom.fs_name)} not found for platform {hl(rom.platform_display_name, color=BLUE)}[{hl(rom.platform_slug)}], deleting database entry only"
                    )

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

            successful_items += 1
        except Exception as e:
            failed_items += 1
            errors.append(f"Failed to delete ROM {id}: {str(e)}")

    if successful_items:
        db_rom_handler.invalidate_filter_values_cache()

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
    data: Annotated[RomUserData, Body()],
    update_last_played: Annotated[
        bool, Query(description="Set last played timestamp to now.")
    ] = False,
    remove_last_played: Annotated[
        bool, Query(description="Clear the last played timestamp.")
    ] = False,
) -> RomUserSchema:
    """Update rom data associated to the current user."""
    rom = db_rom_handler.get_rom(id)

    if not rom:
        raise RomNotFoundInDatabaseException(id)

    assert_rom_visible(request, rom)

    db_rom_user = db_rom_handler.get_rom_user(
        id, request.user.id
    ) or db_rom_handler.add_rom_user(id, request.user.id)

    if update_last_played and remove_last_played:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="update_last_played and remove_last_played are mutually exclusive.",
        )

    cleaned_data = data.model_dump(exclude_unset=True)

    if update_last_played:
        cleaned_data.update({"last_played": datetime.now(timezone.utc)})
    elif remove_last_played:
        cleaned_data.update({"last_played": None})

    rom_user = db_rom_handler.update_rom_user(db_rom_user.id, cleaned_data)

    if "hidden" in cleaned_data:
        db_rom_handler.invalidate_filter_values_cache()

    return RomUserSchema.model_validate(rom_user)
