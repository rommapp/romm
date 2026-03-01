import json
from datetime import datetime
from io import BytesIO
from typing import Annotated

from fastapi import File, Form
from fastapi import Path as PathVar
from fastapi import Query, Request, UploadFile, status

from decorators.auth import protected_route
from endpoints.responses.collection import (
    CollectionSchema,
    SmartCollectionSchema,
    VirtualCollectionSchema,
)
from exceptions.endpoint_exceptions import (
    CollectionAlreadyExistsException,
    CollectionNotFoundInDatabaseException,
    CollectionPermissionError,
)
from handler.auth.constants import Scope
from handler.database import db_collection_handler
from handler.filesystem import fs_resource_handler
from handler.filesystem.base_handler import CoverSize
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.collection import (
    Collection,
    SmartCollection,
    VirtualCollection,
)
from utils.router import APIRouter

router = APIRouter(
    prefix="/collections",
    tags=["collections"],
)


@protected_route(router.post, "", [Scope.COLLECTIONS_WRITE])
async def add_collection(
    request: Request,
    is_public: bool | None = None,
    is_favorite: bool | None = None,
    artwork: UploadFile | None = File(
        default=None, description="Collection artwork file."
    ),
    name: str = Form(default=""),
    description: str = Form(default=""),
    url_cover: str = Form(
        default="", description="Remote URL to fetch and use as cover artwork."
    ),
) -> CollectionSchema:
    """Create collection endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        CollectionSchema: Just created collection
    """
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

    if artwork is not None and artwork.filename is not None:
        file_ext = artwork.filename.split(".")[-1]
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

    return CollectionSchema.model_validate(created_collection)


@protected_route(router.post, "/smart", [Scope.COLLECTIONS_WRITE])
async def add_smart_collection(
    request: Request,
    is_public: bool | None = None,
    name: str = Form(default=""),
    description: str = Form(default=""),
    filter_criteria: str = Form(
        default="{}",
        description="Smart collection filters as a JSON string.",
    ),
) -> SmartCollectionSchema:
    """Create smart collection endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        SmartCollectionSchema: Just created smart collection
    """
    # Parse filter criteria from JSON string
    try:
        parsed_filter_criteria = json.loads(filter_criteria)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid JSON for filter_criteria field") from e

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

    # Fetch the ROMs to update the database model
    smart_collection = created_smart_collection.update_properties(request.user.id)

    return SmartCollectionSchema.model_validate(smart_collection)


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
    """Get collections endpoint

    Args:
        request (Request): Fastapi Request object
        updated_after: Filter collections updated after this datetime

    Returns:
        list[CollectionSchema]: List of collections
    """

    collections = db_collection_handler.get_collections(updated_after=updated_after)

    return CollectionSchema.for_user(request.user.id, collections)


@protected_route(router.get, "/identifiers", [Scope.COLLECTIONS_READ])
def get_collection_identifiers(
    request: Request,
) -> list[int]:
    """Get collections identifiers endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[int]: List of collection IDs
    """

    collections = db_collection_handler.get_collections(
        only_fields=[
            Collection.id,
            Collection.name,
            Collection.user_id,
            Collection.is_public,
        ],
    )

    return [c.id for c in collections if c.user_id == request.user.id or c.is_public]


@protected_route(router.get, "/virtual", [Scope.COLLECTIONS_READ])
def get_virtual_collections(
    request: Request,
    type: str,
    limit: int | None = None,
) -> list[VirtualCollectionSchema]:
    """Get virtual collections endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[VirtualCollectionSchema]: List of virtual collections
    """

    virtual_collections = db_collection_handler.get_virtual_collections(
        type=type, limit=limit
    )

    return [VirtualCollectionSchema.model_validate(vc) for vc in virtual_collections]


@protected_route(router.get, "/virtual/identifiers", [Scope.COLLECTIONS_READ])
def get_virtual_collection_identifiers(
    request: Request,
) -> list[str]:
    """Get virtual collections identifiers endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[str]: List of generated virtual collection IDs
    """

    virtual_collections = db_collection_handler.get_virtual_collections(
        type="all",
        only_fields=[VirtualCollection.name, VirtualCollection.type],
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
    """Get smart collections endpoint

    Args:
        request (Request): Fastapi Request object
        updated_after: Filter smart collections updated after this datetime

    Returns:
        list[SmartCollectionSchema]: List of smart collections
    """

    smart_collections = db_collection_handler.get_smart_collections(
        request.user.id, updated_after=updated_after
    )

    return SmartCollectionSchema.for_user(request.user.id, smart_collections)


@protected_route(router.get, "/smart/identifiers", [Scope.COLLECTIONS_READ])
def get_smart_collection_identifiers(
    request: Request,
) -> list[int]:
    """Get smart collections identifiers endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[int]: List of smart collection IDs
    """

    smart_collections = db_collection_handler.get_smart_collections(
        request.user.id,
        only_fields=[SmartCollection.id],
    )

    return [s.id for s in smart_collections]


@protected_route(router.get, "/{id}", [Scope.COLLECTIONS_READ])
def get_collection(request: Request, id: int) -> CollectionSchema:
    """Get collections endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Collection id. Defaults to None.

    Returns:
        CollectionSchema: Collection
    """

    collection = db_collection_handler.get_collection(id)
    if not collection:
        raise CollectionNotFoundInDatabaseException(id)

    if collection.user_id != request.user.id and not collection.is_public:
        raise CollectionPermissionError(id)

    return CollectionSchema.model_validate(collection)


@protected_route(router.get, "/virtual/{id}", [Scope.COLLECTIONS_READ])
def get_virtual_collection(request: Request, id: str) -> VirtualCollectionSchema:
    """Get virtual collections endpoint

    Args:
        request (Request): Fastapi Request object
        id (str): Virtual collection id

    Returns:
        VirtualCollectionSchema: Virtual collection
    """

    virtual_collection = db_collection_handler.get_virtual_collection(id)
    if not virtual_collection:
        raise CollectionNotFoundInDatabaseException(id)

    return VirtualCollectionSchema.model_validate(virtual_collection)


@protected_route(router.get, "/smart/{id}", [Scope.COLLECTIONS_READ])
def get_smart_collection(request: Request, id: int) -> SmartCollectionSchema:
    """Get smart collection endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Smart collection id

    Returns:
        SmartCollectionSchema: Smart collection
    """

    smart_collection = db_collection_handler.get_smart_collection(id)
    if not smart_collection:
        raise CollectionNotFoundInDatabaseException(id)

    if smart_collection.user_id != request.user.id and not smart_collection.is_public:
        raise CollectionPermissionError(id)

    return SmartCollectionSchema.model_validate(smart_collection)


@protected_route(router.put, "/{id}", [Scope.COLLECTIONS_WRITE])
async def update_collection(
    request: Request,
    id: int,
    remove_cover: bool = False,
    is_public: bool | None = None,
    artwork: UploadFile | None = File(
        default=None, description="Collection artwork file."
    ),
    rom_ids: str = Form(
        ...,
        description="Collection ROM IDs as a JSON array string (e.g. [1,2,3]).",
    ),
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    url_cover: str | None = Form(default=None, description="Updated remote cover URL."),
) -> CollectionSchema:
    """Update collection endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        CollectionSchema: Updated collection
    """
    collection = db_collection_handler.get_collection(id)
    if not collection:
        raise CollectionNotFoundInDatabaseException(id)

    if collection.user_id != request.user.id:
        raise CollectionPermissionError(id)

    if not collection:
        raise CollectionNotFoundInDatabaseException(id)

    try:
        parsed_rom_ids = json.loads(rom_ids)
    except json.JSONDecodeError as e:
        raise ValueError("Invalid list for rom_ids field in update collection") from e

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
            file_ext = artwork.filename.split(".")[-1]
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

    updated_collection = db_collection_handler.update_collection(
        id, cleaned_data, parsed_rom_ids
    )

    return CollectionSchema.model_validate(updated_collection)


@protected_route(router.put, "/smart/{id}", [Scope.COLLECTIONS_WRITE])
async def update_smart_collection(
    request: Request,
    id: int,
    is_public: bool | None = None,
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    filter_criteria: str | None = Form(
        default=None,
        description="Updated smart collection filters as a JSON string.",
    ),
) -> SmartCollectionSchema:
    """Update smart collection endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Smart collection id

    Returns:
        SmartCollectionSchema: Updated smart collection
    """
    smart_collection = db_collection_handler.get_smart_collection(id)
    if not smart_collection:
        raise CollectionNotFoundInDatabaseException(id)

    if smart_collection.user_id != request.user.id:
        raise CollectionPermissionError(id)

    # Parse filter criteria if provided
    parsed_filter_criteria = smart_collection.filter_criteria
    if filter_criteria is not None:
        try:
            parsed_filter_criteria = json.loads(filter_criteria)
        except json.JSONDecodeError as e:
            raise ValueError("Invalid JSON for filter_criteria field") from e

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

    # Fetch the ROMs to update the database model
    smart_collection = updated_smart_collection.update_properties(request.user.id)

    return SmartCollectionSchema.model_validate(smart_collection)


@protected_route(
    router.delete,
    "/{id}",
    [Scope.COLLECTIONS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_collection(
    request: Request,
    id: Annotated[int, PathVar(description="Collection internal id.", ge=1)],
) -> None:
    """Delete a collection by ID."""
    collection = db_collection_handler.get_collection(id)
    if not collection:
        raise CollectionNotFoundInDatabaseException(id)

    if collection.user_id != request.user.id:
        raise CollectionPermissionError(id)

    log.info(f"Deleting {hl(collection.name, color=BLUE)} from database")
    db_collection_handler.delete_collection(id)

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
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_smart_collection(
    request: Request,
    id: Annotated[int, PathVar(description="Smart collection internal id.", ge=1)],
) -> None:
    """Delete a smart collection by ID."""
    smart_collection = db_collection_handler.get_smart_collection(id)
    if not smart_collection:
        raise CollectionNotFoundInDatabaseException(id)

    if smart_collection.user_id != request.user.id:
        raise CollectionPermissionError(id)

    log.info(f"Deleting {hl(smart_collection.name, color=BLUE)} from database")
    db_collection_handler.delete_smart_collection(id)
