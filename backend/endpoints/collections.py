from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.collection import CollectionSchema
from exceptions.endpoint_exceptions import CollectionNotFoundInDatabaseException
from fastapi import APIRouter, Request
from handler.database import db_collection_handler
from handler.filesystem import fs_collection_handler
from logger.logger import log

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
    cleaned_data = {}
    cleaned_data["name"] = data["name"]
    cleaned_data["description"] = data["description"]
    cleaned_data["user_id"] = request.user.id
    return fs_collection_handler.add_collection(cleaned_data)


@protected_route(router.get, "/collections", ["collections.read"])
def get_collections(request: Request) -> list[CollectionSchema]:
    """Get collections endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Collection id. Defaults to None.

    Returns:
        list[CollectionSchema]: List of collections
    """

    return db_collection_handler.get_collections()


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
async def update_collection(request: Request) -> MessageResponse:
    """Update collection endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        MessageResponse: Standard message response
    """

    return {"msg": "Enpoint not available yet"}


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

    log.info(f"Deleting {collection.name} [{collection.fs_slug}] from database")
    db_collection_handler.delete_collection(id)

    return {"msg": f"{collection.name} - [{collection.fs_slug}] deleted successfully!"}
