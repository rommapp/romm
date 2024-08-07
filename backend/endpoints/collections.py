import json
from shutil import rmtree

from anyio import open_file
from config import RESOURCES_BASE_PATH
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.collection import CollectionSchema
from exceptions.endpoint_exceptions import (
    CollectionAlreadyExistsException,
    CollectionNotFoundInDatabaseException,
    CollectionPermissionError,
)
from fastapi import Request, UploadFile
from handler.database import db_collection_handler
from handler.filesystem import fs_resource_handler
from handler.filesystem.base_handler import CoverSize
from logger.logger import log
from models.collection import Collection
from sqlalchemy.inspection import inspect
from utils.router import APIRouter

router = APIRouter()


@protected_route(router.post, "/collections", ["collections.write"])
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

    if artwork is not None:
        file_ext = artwork.filename.split(".")[-1]
        (
            path_cover_l,
            path_cover_s,
            artwork_path,
        ) = await fs_resource_handler.build_artwork_path(_added_collection, file_ext)

        artwork_file = artwork.file.read()
        file_location_s = f"{artwork_path}/small.{file_ext}"
        async with await open_file(file_location_s, "wb+") as artwork_s:
            await artwork_s.write(artwork_file)
            fs_resource_handler.resize_cover_to_small(file_location_s)

        file_location_l = f"{artwork_path}/big.{file_ext}"
        async with await open_file(file_location_l, "wb+") as artwork_l:
            await artwork_l.write(artwork_file)
    else:
        path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
            overwrite=True,
            entity=_added_collection,
            url_cover=_added_collection.url_cover,
        )

    _added_collection.path_cover_s = path_cover_s
    _added_collection.path_cover_l = path_cover_l
    # Update the collection with the cover path and update database
    return db_collection_handler.update_collection(
        _added_collection.id,
        {
            c: getattr(_added_collection, c)
            for c in inspect(_added_collection).mapper.column_attrs.keys()
        },
    )


@protected_route(router.get, "/collections", ["collections.read"])
def get_collections(request: Request) -> list[CollectionSchema]:
    """Get collections endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Collection id. Defaults to None.

    Returns:
        list[CollectionSchema]: List of collections
    """

    collections = db_collection_handler.get_collections()
    return CollectionSchema.for_user(request.user.id, collections)


@protected_route(router.get, "/collections/{id}", ["collections.read"])
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

    return collection


@protected_route(router.put, "/collections/{id}", ["collections.write"])
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

    if collection.user_id != request.user.id:
        raise CollectionPermissionError(id)

    if not collection:
        raise CollectionNotFoundInDatabaseException(id)

    try:
        roms = json.loads(data["roms"])
    except json.JSONDecodeError as e:
        raise ValueError("Invalid list for roms field in update collection") from e
    except KeyError:
        roms = collection.roms

    cleaned_data = {
        "name": data.get("name", collection.name),
        "description": data.get("description", collection.description),
        "is_public": is_public if is_public is not None else collection.is_public,
        "roms": list(set(roms)),
        "user_id": request.user.id,
    }

    if remove_cover:
        cleaned_data.update(fs_resource_handler.remove_cover(collection))
        cleaned_data.update({"url_cover": ""})
    else:
        if artwork is not None:
            file_ext = artwork.filename.split(".")[-1]
            (
                path_cover_l,
                path_cover_s,
                artwork_path,
            ) = await fs_resource_handler.build_artwork_path(collection, file_ext)

            cleaned_data["path_cover_l"] = path_cover_l
            cleaned_data["path_cover_s"] = path_cover_s

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
            if data.get("url_cover", "") != collection.url_cover or not (
                await fs_resource_handler.cover_exists(collection, CoverSize.BIG)
            ):
                cleaned_data.update(
                    {"url_cover": data.get("url_cover", collection.url_cover)}
                )
                path_cover_s, path_cover_l = await fs_resource_handler.get_cover(
                    overwrite=True,
                    entity=collection,
                    url_cover=data.get("url_cover", ""),
                )
                cleaned_data.update(
                    {"path_cover_s": path_cover_s, "path_cover_l": path_cover_l}
                )

    return db_collection_handler.update_collection(id, cleaned_data)


@protected_route(router.delete, "/collections/{id}", ["collections.write"])
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

    log.info(f"Deleting {collection.name} from database")
    db_collection_handler.delete_collection(id)

    try:
        rmtree(f"{RESOURCES_BASE_PATH}/{collection.fs_resources_path}")
    except FileNotFoundError:
        log.error(f"Couldn't find resources to delete for {collection.name}")

    return {"msg": f"{collection.name} deleted successfully!"}
