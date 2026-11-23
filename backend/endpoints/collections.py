import json
from collections.abc import Iterable
from datetime import datetime
from io import BytesIO
from typing import Annotated, Any, Final, TypeVar

from fastapi import Body, File, Form, HTTPException
from fastapi import Path as PathVar
from fastapi import Query, Request, UploadFile, status
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from decorators.auth import protected_route
from endpoints.responses.base import BaseModel
from endpoints.responses.collection import (
    CollectionSchema,
    SmartCollectionSchema,
    VirtualCollectionSchema,
)
from endpoints.roms import (
    refresh_affected_smart_collections,
    refresh_scoped_smart_collections,
    reject_local_file_url,
)
from exceptions.endpoint_exceptions import (
    CollectionAlreadyExistsException,
    CollectionNotFoundInDatabaseException,
    CollectionPermissionError,
)
from handler.audit_handler import AuditTarget, changed_fields, record
from handler.auth.constants import Scope
from handler.auth.dependencies import get_rom_visibility_filter
from handler.database import db_collection_handler, db_rom_handler
from handler.database.rom_filters import RomFilterParams
from handler.filesystem import fs_resource_handler
from handler.filesystem.assets_handler import validate_image_upload
from handler.filesystem.base_handler import CoverSize
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.audit_event import AuditAction
from models.collection import (
    COLLECTION_NAME_MAX_LENGTH,
    Collection,
    SmartCollection,
    VirtualCollection,
)
from models.rom import rom_id_from_resource_url
from utils.router import APIRouter
from utils.validation import ValidationError

router = APIRouter(
    prefix="/collections",
    tags=["collections"],
)

COLLECTION_ARTWORK_FILE = File(default=None, description="Collection artwork file.")
ROM_IDS_ADAPTER: Final = TypeAdapter(list[int])

CollectionSchemaT = TypeVar(
    "CollectionSchemaT",
    CollectionSchema,
    SmartCollectionSchema,
)


def _hidden_rom_ids(request: Request, rom_ids: Iterable[int]) -> set[int]:
    """Of `rom_ids`, the ones hidden from the caller."""
    ids = set(rom_ids)
    visibility = get_rom_visibility_filter(request)
    if not ids or visibility.is_unrestricted:
        return set()
    return db_rom_handler.get_hidden_rom_ids_among(list(ids), visibility)


def _hide_collection_roms(
    schemas: list[CollectionSchemaT], request: Request
) -> list[CollectionSchemaT]:
    """Drop roms hidden from the caller from each collection's ids, count and covers."""
    hidden = _hidden_rom_ids(request, (rid for s in schemas for rid in s.rom_ids))
    if not hidden:
        return schemas
    for s in schemas:
        s.rom_ids = set(s.rom_ids) - hidden
        s.path_covers_small = _without_covers(s.path_covers_small, hidden)
        s.path_covers_large = _without_covers(s.path_covers_large, hidden)
    return schemas


def _hide_single_collection_roms(
    schema: CollectionSchemaT, request: Request
) -> CollectionSchemaT:
    return _hide_collection_roms([schema], request)[0]


def _without_covers(urls: list[str], hidden: set[int]) -> list[str]:
    return [u for u in urls if rom_id_from_resource_url(u) not in hidden]


def _record_collection(
    request: Request,
    action: AuditAction,
    collection: Collection | SmartCollection,
    data: dict[str, Any] | None = None,
) -> None:
    # Every heart toggle goes through the favourites collection; that's not news.
    if getattr(collection, "is_favorite", False):
        return
    record(action, request, AuditTarget.of_collection(collection), data)


def _criteria_collection_id(criteria: object) -> int | None:
    filters = RomFilterParams.from_stored_criteria(criteria)
    return filters.collection_id if filters else None


def _parse_filter_criteria(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON for filter_criteria field",
        ) from e
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filter_criteria must be a JSON object",
        )
    return parsed


def _check_criteria_collection(
    criteria: object, user_id: int, kept_id: int | None = None
) -> None:
    """Refuse criteria newly scoped to a collection the owner can't see."""
    collection_id = _criteria_collection_id(criteria)
    if not collection_id or collection_id == kept_id:
        return
    collection = db_collection_handler.get_collection(collection_id)
    if not collection or (collection.user_id != user_id and not collection.is_public):
        raise CollectionNotFoundInDatabaseException(collection_id)


def _visible_or_404[C: (Collection, SmartCollection)](
    request: Request, collection: C | None, id: int
) -> C:
    """Return `collection` if the caller owns it or it is public. Otherwise raise the same 404 as for a missing one."""
    if not collection or (
        collection.user_id != request.user.id and not collection.is_public
    ):
        raise CollectionNotFoundInDatabaseException(id)
    return collection


def _owned_or_error[C: (Collection, SmartCollection)](
    request: Request, collection: C | None, id: int
) -> C:
    """Return `collection` if the caller owns it. Raise 403 if it is public but another user owns it."""
    collection = _visible_or_404(request, collection, id)
    if collection.user_id != request.user.id:
        raise CollectionPermissionError(id)
    return collection


CollectionIdPath = Annotated[int, PathVar(description="The ID of the collection.")]
SmartCollectionIdPath = Annotated[
    int, PathVar(description="The ID of the smart collection.")
]
VirtualCollectionIdPath = Annotated[
    str,
    PathVar(
        description="The ID of the virtual collection, as returned by `GET /collections/virtual`."
    ),
]
IsPublicUpdateQuery = Annotated[
    bool | None,
    Query(
        description=(
            "Whether other users can see the collection. Leave it out to keep"
            " the current setting."
        )
    ),
]
COLLECTION_NAME_FORM = "The name of the collection."
COLLECTION_DESCRIPTION_FORM = "The description of the collection."

ARTWORK_400 = "The cover URL is a local file URL, the artwork is not a PNG, JPEG, WebP, GIF or JPEG XL image, or its dimensions are too large."
FILTER_CRITERIA_400 = "The filter criteria are not a JSON object."
CRITERIA_COLLECTION_404 = "The filter criteria name a collection the caller cannot see."
COLLECTION_404 = {"description": "No collection the caller can see has this ID."}
SMART_COLLECTION_404 = {
    "description": "No smart collection the caller can see has this ID."
}
NOT_OWNER_403 = {"description": "The collection is public, but another user owns it."}
NAME_TAKEN_409 = {"description": "The caller already has a collection with this name."}
SMART_NAME_TAKEN_409 = {
    "description": "The caller already has a smart collection with this name."
}


@protected_route(
    router.post,
    "",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": ARTWORK_400},
        status.HTTP_409_CONFLICT: NAME_TAKEN_409,
    },
)
async def add_collection(
    request: Request,
    is_public: bool | None = None,
    is_favorite: bool | None = None,
    artwork: UploadFile | None = COLLECTION_ARTWORK_FILE,
    name: str = Form(
        default="",
        max_length=COLLECTION_NAME_MAX_LENGTH,
        description=COLLECTION_NAME_FORM,
    ),
    description: str = Form(default="", description=COLLECTION_DESCRIPTION_FORM),
    url_cover: str = Form(
        default="", description="Remote URL to fetch and use as cover artwork."
    ),
) -> CollectionSchema:
    """Create a collection for the caller, with artwork from an upload or from `url_cover`."""
    reject_local_file_url("url_cover", url_cover, None)
    cleaned_data = {
        "name": name,
        "description": description,
        "url_cover": url_cover,
        "is_public": is_public or False,
        "is_favorite": is_favorite or False,
        "user_id": request.user.id,
    }

    db_collection = db_collection_handler.get_collection_by_name(
        cleaned_data["name"], request.user.id
    )

    if db_collection:
        raise CollectionAlreadyExistsException(cleaned_data["name"])

    _added_collection = db_collection_handler.add_collection(Collection(**cleaned_data))

    try:
        if artwork is not None and artwork.filename is not None:
            file_ext = validate_image_upload(
                artwork, label="Artwork", allow_converted=True
            )
            artwork_content = BytesIO(await artwork.read())
            (
                path_cover_l,
                path_cover_s,
            ) = await fs_resource_handler.store_artwork(
                _added_collection, artwork_content, file_ext
            )
        else:
            path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
                entity=_added_collection,
                overwrite=True,
                url_cover=_added_collection.url_cover,
            )
    except ValidationError as e:
        log.error(f"Invalid cover URL in add_collection: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) from e

    _added_collection.path_cover_s = path_cover_s
    _added_collection.path_cover_l = path_cover_l

    # Update the collection with the cover path and update database
    created_collection = db_collection_handler.update_collection(
        _added_collection.id,
        {
            "path_cover_s": path_cover_s,
            "path_cover_l": path_cover_l,
        },
    )

    _record_collection(request, AuditAction.COLLECTION_CREATE, created_collection)
    return CollectionSchema.model_validate(created_collection)


@protected_route(
    router.post,
    "/smart",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": FILTER_CRITERIA_400},
        status.HTTP_404_NOT_FOUND: {"description": CRITERIA_COLLECTION_404},
        status.HTTP_409_CONFLICT: SMART_NAME_TAKEN_409,
    },
)
async def add_smart_collection(
    request: Request,
    is_public: bool | None = None,
    name: str = Form(
        default="",
        max_length=COLLECTION_NAME_MAX_LENGTH,
        description=COLLECTION_NAME_FORM,
    ),
    description: str = Form(default="", description=COLLECTION_DESCRIPTION_FORM),
    filter_criteria: str = Form(
        default="{}",
        description="Smart collection filters as a JSON string.",
    ),
) -> SmartCollectionSchema:
    """Create a smart collection for the caller, holding the roms that match its filter criteria."""
    parsed_filter_criteria = _parse_filter_criteria(filter_criteria)
    _check_criteria_collection(parsed_filter_criteria, request.user.id)

    cleaned_data = {
        "name": name,
        "description": description,
        "filter_criteria": parsed_filter_criteria,
        "is_public": is_public if is_public is not None else False,
        "user_id": request.user.id,
    }

    db_smart_collection = db_collection_handler.get_smart_collection_by_name(
        cleaned_data["name"], request.user.id
    )

    if db_smart_collection:
        raise CollectionAlreadyExistsException(cleaned_data["name"])

    created_smart_collection = db_collection_handler.add_smart_collection(
        SmartCollection(**cleaned_data)
    )

    smart_collection = (
        db_collection_handler.refresh_smart_collection(created_smart_collection.id)
        or created_smart_collection
    )
    _record_collection(request, AuditAction.SMART_COLLECTION_CREATE, smart_collection)

    return _hide_single_collection_roms(
        SmartCollectionSchema.model_validate(smart_collection), request
    )


@protected_route(router.get, "", [Scope.COLLECTIONS_READ])
def get_collections(
    request: Request,
    updated_after: Annotated[
        datetime | None,
        Query(
            description="Filter collections updated after this datetime (ISO 8601 format with timezone information)."
        ),
    ] = None,
) -> list[CollectionSchema]:
    """List the caller's collections and other users' public collections."""

    collections = db_collection_handler.get_collections(updated_after=updated_after)

    return _hide_collection_roms(
        CollectionSchema.for_user(request.user.id, collections), request
    )


@protected_route(router.get, "/identifiers", [Scope.COLLECTIONS_READ])
def get_collection_identifiers(
    request: Request,
) -> list[int]:
    """List the IDs of the caller's collections and of other users' public collections."""

    rows = db_collection_handler.get_collection_ids()

    return [row.id for row in rows if row.user_id == request.user.id or row.is_public]


@protected_route(router.get, "/virtual", [Scope.COLLECTIONS_READ])
def get_virtual_collections(
    request: Request,
    type: Annotated[
        str,
        Query(
            description=(
                "The kind of collection: `genre`, `franchise`, `collection`,"
                " `mode`, `company`, `publisher`, `developer` or `all`. Virtual"
                " collections are generated from the library's metadata, one for"
                " each distinct value."
            )
        ),
    ],
    limit: Annotated[
        int | None,
        Query(
            description=(
                "The maximum number of collections to return, sorted by name."
                " Leave it out to return all of them."
            )
        ),
    ] = None,
) -> list[VirtualCollectionSchema]:
    """List the virtual collections of one kind that hold roms the caller can see."""

    virtual_collections = db_collection_handler.get_virtual_collections(
        type=type, limit=limit, visibility=get_rom_visibility_filter(request)
    )

    return [VirtualCollectionSchema.model_validate(vc) for vc in virtual_collections]


@protected_route(router.get, "/virtual/identifiers", [Scope.COLLECTIONS_READ])
def get_virtual_collection_identifiers(
    request: Request,
) -> list[str]:
    """List the IDs of the virtual collections that hold roms the caller can see."""

    virtual_collections = db_collection_handler.get_virtual_collections(
        type="all",
        only_fields=[VirtualCollection.name, VirtualCollection.type],
        visibility=get_rom_visibility_filter(request),
    )

    return [s.id for s in virtual_collections]


@protected_route(router.get, "/smart", [Scope.COLLECTIONS_READ])
def get_smart_collections(
    request: Request,
    updated_after: Annotated[
        datetime | None,
        Query(
            description="Filter smart collections updated after this datetime (ISO 8601 format with timezone information)."
        ),
    ] = None,
) -> list[SmartCollectionSchema]:
    """List the caller's smart collections and other users' public smart collections."""

    smart_collections = db_collection_handler.get_smart_collections(
        request.user.id, updated_after=updated_after
    )

    return _hide_collection_roms(
        SmartCollectionSchema.for_user(request.user.id, smart_collections), request
    )


@protected_route(router.get, "/smart/identifiers", [Scope.COLLECTIONS_READ])
def get_smart_collection_identifiers(
    request: Request,
) -> list[int]:
    """List the IDs of the caller's smart collections and of other users' public smart collections."""

    return db_collection_handler.get_smart_collection_ids(request.user.id)


@protected_route(
    router.get,
    "/{id}",
    [Scope.COLLECTIONS_READ],
    responses={
        status.HTTP_404_NOT_FOUND: COLLECTION_404,
    },
)
def get_collection(request: Request, id: CollectionIdPath) -> CollectionSchema:
    """Get one of the caller's collections, or another user's public collection."""

    collection = _visible_or_404(request, db_collection_handler.get_collection(id), id)

    return _hide_single_collection_roms(
        CollectionSchema.model_validate(collection), request
    )


@protected_route(
    router.get,
    "/virtual/{id}",
    [Scope.COLLECTIONS_READ],
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "No virtual collection with roms the caller can see has this ID."
        }
    },
)
def get_virtual_collection(
    request: Request, id: VirtualCollectionIdPath
) -> VirtualCollectionSchema:
    """Get a virtual collection, leaving out the roms hidden from the caller."""

    virtual_collection = db_collection_handler.get_virtual_collection(
        id, visibility=get_rom_visibility_filter(request)
    )
    if not virtual_collection:
        raise CollectionNotFoundInDatabaseException(id)

    return VirtualCollectionSchema.model_validate(virtual_collection)


@protected_route(
    router.get,
    "/smart/{id}",
    [Scope.COLLECTIONS_READ],
    responses={
        status.HTTP_404_NOT_FOUND: SMART_COLLECTION_404,
    },
)
def get_smart_collection(
    request: Request, id: SmartCollectionIdPath
) -> SmartCollectionSchema:
    """Get one of the caller's smart collections, or another user's public smart collection."""

    smart_collection = _visible_or_404(
        request, db_collection_handler.get_smart_collection(id), id
    )

    return _hide_single_collection_roms(
        SmartCollectionSchema.model_validate(smart_collection), request
    )


@protected_route(
    router.put,
    "/{id}",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": ARTWORK_400},
        status.HTTP_403_FORBIDDEN: NOT_OWNER_403,
        status.HTTP_404_NOT_FOUND: COLLECTION_404,
        status.HTTP_409_CONFLICT: NAME_TAKEN_409,
    },
)
async def update_collection(
    request: Request,
    id: CollectionIdPath,
    remove_cover: Annotated[
        bool,
        Query(description="Whether to delete the cover and its URL."),
    ] = False,
    is_public: IsPublicUpdateQuery = None,
    artwork: UploadFile | None = COLLECTION_ARTWORK_FILE,
    rom_ids: str = Form(
        ...,
        description="Collection ROM IDs as a JSON array string (e.g. [1,2,3]).",
    ),
    name: str | None = Form(
        default=None,
        max_length=COLLECTION_NAME_MAX_LENGTH,
        description="The new name. Leave it out to keep the current name.",
    ),
    description: str | None = Form(
        default=None,
        description="The new description. Leave it out to keep the current description.",
    ),
    url_cover: str | None = Form(default=None, description="Updated remote cover URL."),
) -> CollectionSchema:
    """Update one of the caller's collections and replace its roms with `rom_ids`, leaving the roms the caller cannot see as they are."""
    collection = _owned_or_error(request, db_collection_handler.get_collection(id), id)
    reject_local_file_url("url_cover", url_cover, collection.url_cover)

    if name is not None:
        namesake = db_collection_handler.get_collection_by_name(name, request.user.id)
        if namesake and namesake.id != collection.id:
            raise CollectionAlreadyExistsException(name)

    try:
        parsed_rom_ids = ROM_IDS_ADAPTER.validate_json(rom_ids, strict=True)
    except PydanticValidationError as e:
        raise HTTPException(
            status_code=422,
            detail="Invalid list for rom_ids field in update collection",
        ) from e
    # The caller can't add roms hidden from them, nor drop members they can't see.
    hidden = _hidden_rom_ids(request, [*parsed_rom_ids, *collection.rom_ids])
    parsed_rom_ids = [rid for rid in parsed_rom_ids if rid not in hidden] + sorted(
        hidden & set(collection.rom_ids)
    )

    cleaned_data = {
        "name": name if name is not None else collection.name,
        "description": (
            description if description is not None else collection.description
        ),
        "is_public": is_public if is_public is not None else collection.is_public,
        "user_id": request.user.id,
    }

    if remove_cover:
        cleaned_data.update(await fs_resource_handler.remove_cover(collection))
        cleaned_data.update({"url_cover": ""})
    else:
        if artwork is not None and artwork.filename is not None:
            file_ext = validate_image_upload(
                artwork, label="Artwork", allow_converted=True
            )
            artwork_content = BytesIO(await artwork.read())
            (
                path_cover_l,
                path_cover_s,
            ) = await fs_resource_handler.store_artwork(
                collection, artwork_content, file_ext
            )

            cleaned_data.update(
                {
                    "url_cover": "",
                    "path_cover_s": path_cover_s,
                    "path_cover_l": path_cover_l,
                }
            )
        else:
            current_url_cover = (
                url_cover if url_cover is not None else collection.url_cover
            )
            if (
                current_url_cover != collection.url_cover
                or not fs_resource_handler.cover_exists(collection, CoverSize.BIG)
            ):
                try:
                    path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
                        entity=collection,
                        overwrite=True,
                        url_cover=current_url_cover,
                    )
                    cleaned_data.update(
                        {
                            "url_cover": current_url_cover,
                            "path_cover_s": path_cover_s,
                            "path_cover_l": path_cover_l,
                        }
                    )
                except ValidationError as e:
                    log.error(f"Invalid cover URL in update_collection: {str(e)}")
                    raise HTTPException(status_code=400, detail=str(e)) from e

    updated_collection = db_collection_handler.update_collection(
        id, cleaned_data, parsed_rom_ids
    )
    changed = changed_fields(
        collection, cleaned_data, ("name", "description", "is_public")
    )
    if "is_public" in changed:
        refresh_scoped_smart_collections(id)
    new_artwork = artwork is not None and artwork.filename is not None
    if (
        remove_cover
        or new_artwork
        or changed_fields(collection, cleaned_data, ["url_cover"])
    ):
        changed.append("cover")
    before_ids, after_ids = set(collection.rom_ids), set(updated_collection.rom_ids)
    if before_ids != after_ids:
        refresh_affected_smart_collections(
            sorted(before_ids ^ after_ids), membership_only=True
        )
    if changed or before_ids != after_ids:
        _record_collection(
            request,
            AuditAction.COLLECTION_EDIT,
            updated_collection,
            {
                "changed": changed,
                "added": len(after_ids - before_ids),
                "removed": len(before_ids - after_ids),
            },
        )

    return _hide_single_collection_roms(
        CollectionSchema.model_validate(updated_collection), request
    )


@protected_route(
    router.put,
    "/{id}/visibility",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_403_FORBIDDEN: NOT_OWNER_403,
        status.HTTP_404_NOT_FOUND: COLLECTION_404,
    },
)
def update_collection_visibility(
    request: Request,
    id: CollectionIdPath,
    is_public: Annotated[
        bool,
        Body(embed=True),
    ],
) -> CollectionSchema:
    """Share or unshare a collection (owner only), leaving its games and cover."""
    collection = _owned_or_error(request, db_collection_handler.get_collection(id), id)

    updated_collection = db_collection_handler.update_collection(
        id, {"is_public": is_public}
    )
    if collection.is_public != is_public:
        refresh_scoped_smart_collections(id)

    return _hide_single_collection_roms(
        CollectionSchema.model_validate(updated_collection), request
    )


class CollectionRomsPayload(BaseModel):
    rom_ids: list[int]


@protected_route(
    router.post,
    "/{id}/roms",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_403_FORBIDDEN: NOT_OWNER_403,
        status.HTTP_404_NOT_FOUND: COLLECTION_404,
    },
)
async def add_roms_to_collection(
    request: Request,
    id: CollectionIdPath,
    payload: CollectionRomsPayload,
) -> CollectionSchema:
    """Add roms to one of the caller's collections in one step, keeping the roms it already holds."""
    collection = _owned_or_error(request, db_collection_handler.get_collection(id), id)

    hidden = _hidden_rom_ids(request, payload.rom_ids)
    rom_ids = [rid for rid in payload.rom_ids if rid not in hidden]
    before = set(collection.rom_ids)
    updated_collection = db_collection_handler.add_roms_to_collection(id, rom_ids)
    refresh_affected_smart_collections(rom_ids, membership_only=True)
    if added := sorted(set(updated_collection.rom_ids) - before):
        _record_collection(
            request,
            AuditAction.COLLECTION_ADD_ROMS,
            collection,
            {"count": len(added), "rom_ids": added},
        )
    return _hide_single_collection_roms(
        CollectionSchema.model_validate(updated_collection), request
    )


@protected_route(
    router.delete,
    "/{id}/roms",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_403_FORBIDDEN: NOT_OWNER_403,
        status.HTTP_404_NOT_FOUND: COLLECTION_404,
    },
)
async def remove_roms_from_collection(
    request: Request,
    id: CollectionIdPath,
    payload: CollectionRomsPayload,
) -> CollectionSchema:
    """Remove roms from one of the caller's collections in one step, keeping the other roms it holds."""
    collection = _owned_or_error(request, db_collection_handler.get_collection(id), id)

    # Members hidden from the caller stay, as in update_collection.
    hidden = _hidden_rom_ids(request, payload.rom_ids)
    rom_ids = [rid for rid in payload.rom_ids if rid not in hidden]
    before = set(collection.rom_ids)
    updated_collection = db_collection_handler.remove_roms_from_collection(id, rom_ids)
    refresh_affected_smart_collections(rom_ids, membership_only=True)
    if removed := sorted(before - set(updated_collection.rom_ids)):
        _record_collection(
            request,
            AuditAction.COLLECTION_REMOVE_ROMS,
            collection,
            {"count": len(removed), "rom_ids": removed},
        )
    return _hide_single_collection_roms(
        CollectionSchema.model_validate(updated_collection), request
    )


@protected_route(
    router.put,
    "/smart/{id}",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": FILTER_CRITERIA_400},
        status.HTTP_403_FORBIDDEN: NOT_OWNER_403,
        status.HTTP_404_NOT_FOUND: {
            "description": "No smart collection the caller can see has this ID, or the filter criteria name a collection the caller cannot see."
        },
        status.HTTP_409_CONFLICT: SMART_NAME_TAKEN_409,
    },
)
async def update_smart_collection(
    request: Request,
    id: SmartCollectionIdPath,
    is_public: IsPublicUpdateQuery = None,
    name: str | None = Form(
        default=None,
        max_length=COLLECTION_NAME_MAX_LENGTH,
        description="The new name. Leave it out to keep the current name.",
    ),
    description: str | None = Form(
        default=None,
        description="The new description. Leave it out to keep the current description.",
    ),
    filter_criteria: str | None = Form(
        default=None,
        description="Updated smart collection filters as a JSON string.",
    ),
) -> SmartCollectionSchema:
    """Update one of the caller's smart collections. Fields left out of the request keep their current values."""
    smart_collection = _owned_or_error(
        request, db_collection_handler.get_smart_collection(id), id
    )

    if name is not None:
        namesake = db_collection_handler.get_smart_collection_by_name(
            name, request.user.id
        )
        if namesake and namesake.id != smart_collection.id:
            raise CollectionAlreadyExistsException(name)

    # Parse filter criteria if provided
    parsed_filter_criteria = smart_collection.filter_criteria
    if filter_criteria is not None:
        parsed_filter_criteria = _parse_filter_criteria(filter_criteria)
        # The form resends the stored scope on every edit; the ROM filters
        # already match nothing for one the owner has since lost.
        _check_criteria_collection(
            parsed_filter_criteria,
            request.user.id,
            kept_id=_criteria_collection_id(smart_collection.filter_criteria),
        )

    cleaned_data = {
        "name": name if name is not None else smart_collection.name,
        "description": (
            description if description is not None else smart_collection.description
        ),
        "filter_criteria": parsed_filter_criteria,
        "is_public": is_public if is_public is not None else smart_collection.is_public,
        "user_id": request.user.id,
    }

    updated_smart_collection = db_collection_handler.update_smart_collection(
        id, cleaned_data
    )

    smart_collection = (
        db_collection_handler.refresh_smart_collection(id) or updated_smart_collection
    )
    _record_collection(request, AuditAction.SMART_COLLECTION_EDIT, smart_collection)

    return _hide_single_collection_roms(
        SmartCollectionSchema.model_validate(smart_collection), request
    )


@protected_route(
    router.put,
    "/smart/{id}/visibility",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_403_FORBIDDEN: NOT_OWNER_403,
        status.HTTP_404_NOT_FOUND: SMART_COLLECTION_404,
    },
)
def update_smart_collection_visibility(
    request: Request,
    id: SmartCollectionIdPath,
    is_public: Annotated[
        bool,
        Body(embed=True),
    ],
) -> SmartCollectionSchema:
    """Share or unshare a smart collection (owner only), leaving its filters."""
    _owned_or_error(request, db_collection_handler.get_smart_collection(id), id)

    return _hide_single_collection_roms(
        SmartCollectionSchema.model_validate(
            db_collection_handler.update_smart_collection(id, {"is_public": is_public})
        ),
        request,
    )


@protected_route(
    router.delete,
    "/{id}",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_403_FORBIDDEN: NOT_OWNER_403,
        status.HTTP_404_NOT_FOUND: COLLECTION_404,
    },
)
async def delete_collection(
    request: Request,
    id: Annotated[int, PathVar(description="The ID of the collection.", ge=1)],
) -> None:
    """Delete a collection by ID."""
    collection = _owned_or_error(request, db_collection_handler.get_collection(id), id)

    log.info(f"Deleting {hl(collection.name, color=BLUE)} from database")
    db_collection_handler.delete_collection(id)
    refresh_scoped_smart_collections(id)
    _record_collection(request, AuditAction.COLLECTION_DELETE, collection)

    try:
        await fs_resource_handler.remove_directory(collection.fs_resources_path)
    except FileNotFoundError:
        log.error(
            f"Couldn't find resources to delete for {hl(collection.name, color=BLUE)}"
        )


@protected_route(
    router.delete,
    "/smart/{id}",
    [Scope.COLLECTIONS_WRITE],
    responses={
        status.HTTP_403_FORBIDDEN: NOT_OWNER_403,
        status.HTTP_404_NOT_FOUND: SMART_COLLECTION_404,
    },
)
async def delete_smart_collection(
    request: Request,
    id: Annotated[int, PathVar(description="The ID of the smart collection.", ge=1)],
) -> None:
    """Delete a smart collection by ID."""
    smart_collection = _owned_or_error(
        request, db_collection_handler.get_smart_collection(id), id
    )

    log.info(f"Deleting {hl(smart_collection.name, color=BLUE)} from database")
    db_collection_handler.delete_smart_collection(id)
    _record_collection(request, AuditAction.SMART_COLLECTION_DELETE, smart_collection)
