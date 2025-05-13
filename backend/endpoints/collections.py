import json
from io import BytesIO
from shutil import rmtree

from anyio import Path
from config import RESOURCES_BASE_PATH
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.collection import CollectionSchema, VirtualCollectionSchema
from exceptions.endpoint_exceptions import (
    CollectionAlreadyExistsException,
    CollectionNotFoundInDatabaseException,
    CollectionPermissionError,
)
from fastapi import Request, UploadFile
from handler.auth.constants import Scope
from handler.database import db_collection_handler
from handler.filesystem import fs_resource_handler
from handler.filesystem.base_handler import CoverSize
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from models.collection import Collection
from PIL import Image
from sqlalchemy.inspection import inspect
from utils.router import APIRouter

router = APIRouter(
    prefix="/collections",
    tags=["collections"],
)


@protected_route(router.post, "", [Scope.COLLECTIONS_WRITE])
async def add_collection(
    request: Request,
    artwork: UploadFile | None = None,
) -> CollectionSchema:
    """Create collection endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        CollectionSchema: Just created collection
    """

    data = await request.form()
    cleaned_data = {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "url_cover": data.get("url_cover", ""),
        "is_public": data.get("is_public", False),
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
        (
            path_cover_l,
            path_cover_s,
            artwork_path,
        ) = await fs_resource_handler.build_artwork_path(_added_collection, file_ext)

        artwork_content = BytesIO(await artwork.read())
        file_location_small = Path(f"{artwork_path}/small.{file_ext}")
        file_location_large = Path(f"{artwork_path}/big.{file_ext}")
        with Image.open(artwork_content) as img:
            img.save(file_location_large)
            fs_resource_handler.resize_cover_to_small(
                img, save_path=file_location_small
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
            c: getattr(_added_collection, c)
            for c in inspect(_added_collection).mapper.column_attrs.keys()
        },
    )

    return CollectionSchema.model_validate(created_collection)


@protected_route(router.get, "", [Scope.COLLECTIONS_READ])
def get_collections(request: Request) -> list[CollectionSchema]:
    """Get collections endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Collection id. Defaults to None.

    Returns:
        list[CollectionSchema]: List of collections
    """

    collections = db_collection_handler.get_collections()

    return CollectionSchema.for_user(request.user.id, [c for c in collections])


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

    virtual_collections = db_collection_handler.get_virtual_collections(type, limit)

    return [VirtualCollectionSchema.model_validate(vc) for vc in virtual_collections]


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


@protected_route(router.put, "/{id}", [Scope.COLLECTIONS_WRITE])
async def update_collection(
    request: Request,
    id: int,
    remove_cover: bool = False,
    is_public: bool | None = None,
    artwork: UploadFile | None = None,
) -> CollectionSchema:
    """Update collection endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        MessageResponse: Standard message response
    """

    data = await request.form()

    collection = db_collection_handler.get_collection(id)
    if not collection:
        raise CollectionNotFoundInDatabaseException(id)

    if collection.user_id != request.user.id:
        raise CollectionPermissionError(id)

    if not collection:
        raise CollectionNotFoundInDatabaseException(id)

    try:
        rom_ids = json.loads(data["rom_ids"])  # type: ignore
    except json.JSONDecodeError as e:
        raise ValueError("Invalid list for rom_ids field in update collection") from e

    cleaned_data = {
        "name": data.get("name", collection.name),
        "description": data.get("description", collection.description),
        "is_public": is_public if is_public is not None else collection.is_public,
        "user_id": request.user.id,
    }

    if remove_cover:
        cleaned_data.update(fs_resource_handler.remove_cover(collection))
        cleaned_data.update({"url_cover": ""})
    else:
        if artwork is not None and artwork.filename is not None:
            file_ext = artwork.filename.split(".")[-1]
            (
                path_cover_l,
                path_cover_s,
                artwork_path,
            ) = await fs_resource_handler.build_artwork_path(collection, file_ext)

            cleaned_data["path_cover_l"] = path_cover_l
            cleaned_data["path_cover_s"] = path_cover_s

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
            if data.get("url_cover", "") != collection.url_cover or not (
                await fs_resource_handler.cover_exists(collection, CoverSize.BIG)
            ):
                cleaned_data.update(
                    {"url_cover": data.get("url_cover", collection.url_cover)}
                )
                path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
                    entity=collection,
                    overwrite=True,
                    url_cover=data.get("url_cover", ""),  # type: ignore
                )
                cleaned_data.update(
                    {"path_cover_s": path_cover_s, "path_cover_l": path_cover_l}
                )

    updated_collection = db_collection_handler.update_collection(
        id, cleaned_data, rom_ids
    )

    return CollectionSchema.model_validate(updated_collection)


@protected_route(router.delete, "/{id}", [Scope.COLLECTIONS_WRITE])
async def delete_collections(request: Request, id: int) -> MessageResponse:
    """Delete collections endpoint

    Args:
        request (Request): Fastapi Request object
        {
            "collections": List of rom's ids to delete
        }

    Raises:
        HTTPException: Collection not found

    Returns:
        MessageResponse: Standard message response
    """

    collection = db_collection_handler.get_collection(id)

    if not collection:
        raise CollectionNotFoundInDatabaseException(id)

    log.info(f"Deleting {hl(collection.name, color=BLUE)} from database")
    db_collection_handler.delete_collection(id)

    try:
        rmtree(f"{RESOURCES_BASE_PATH}/{collection.fs_resources_path}")
    except FileNotFoundError:
        log.error(
            f"Couldn't find resources to delete for {hl(collection.name, color=BLUE)}"
        )

    return {"msg": f"{collection.name} deleted successfully!"}
