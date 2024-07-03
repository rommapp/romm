import json

from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.collection import CollectionSchema
from exceptions.endpoint_exceptions import (
    CollectionAlreadyExistsException,
    CollectionNotFoundInDatabaseException,
    CollectionPermissionError,
)
from fastapi import APIRouter, Request
from handler.database import db_collection_handler
from logger.logger import log
from models.collection import Collection

router = APIRouter()


@protected_route(router.post, "/collections", ["collections.write"])
async def add_collection(request: Request) -> CollectionSchema:
    """Create collection endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        CollectionSchema: Just created collection
    """

    data = await request.json()
    cleaned_data = {
        "name": data["name"],
        "description": data["description"],
        "user_id": request.user.id,
    }
    collection_db = db_collection_handler.get_collection_by_name(
        cleaned_data["name"], request.user.id
    )
    if collection_db:
        raise CollectionAlreadyExistsException(cleaned_data["name"])
    collection = Collection(**cleaned_data)
    return db_collection_handler.add_collection(collection)


@protected_route(router.get, "/collections", ["collections.read"])
def get_collections(request: Request) -> list[CollectionSchema]:
    """Get collections endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Collection id. Defaults to None.

    Returns:
        list[CollectionSchema]: List of collections
    """

    return db_collection_handler.get_collections(user_id=request.user.id)


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
async def update_collection(request: Request, id: int) -> MessageResponse:
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
        try:
            roms = json.loads(data["roms"])
        except json.JSONDecodeError as e:
            raise ValueError("Invalid list for roms field in update collection") from e
    except KeyError:
        roms = collection.roms

    cleaned_data = {
        "name": data.get("name", collection.name),
        "description": data.get("description", collection.description),
        "roms": list(set(roms)),
        "is_public": data.get("is_public", collection.is_public),
        "user_id": request.user.id,
    }

    db_collection_handler.update_collection(id, cleaned_data)
    return {"msg": "Collection updated  successfully!"}


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

    return {"msg": f"{collection.name} deleted successfully!"}
