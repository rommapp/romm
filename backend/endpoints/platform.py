from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.platform import PlatformSchema
from fastapi import APIRouter, HTTPException, Request, status
from handler import db_platform_handler, igdb_handler
from logger.logger import log

router = APIRouter()


@protected_route(router.post, "/platforms", ["platforms.write"])
async def add_platforms(request: Request) -> MessageResponse:
    """Create platform endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        MessageResponse: Standard message response
    """

    data = await request.json()
    fs_slug = data["fs_slug"]
    platform = igdb_handler.get_platform(fs_slug)
    log.debug(platform)

    return {"msg": f"Platform created successfully!"}


@protected_route(router.get, "/platforms", ["platforms.read"])
def get_platforms(request: Request) -> list[PlatformSchema]:
    """Get platforms endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Platform id. Defaults to None.

    Returns:
        list[PlatformSchema]: List of platforms
    """

    return db_platform_handler.get_platforms()


@protected_route(router.get, "/platforms/{id}", ["platforms.read"])
def get_platform(request: Request, id: int) -> PlatformSchema:
    """Get platforms endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Platform id. Defaults to None.

    Returns:
        PlatformSchema: Platform
    """

    return db_platform_handler.get_platforms(id)


@protected_route(router.put, "/platforms/{id}", ["platforms.write"])
async def update_platform(request: Request) -> MessageResponse:
    """Update platform endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        MessageResponse: Standard message response
    """

    return {"msg": "Enpoint not available yet"}


@protected_route(router.delete, "/platforms/{id}", ["platforms.write"])
async def delete_platforms(request: Request, id: int) -> MessageResponse:
    """Delete platforms endpoint

    Args:
        request (Request): Fastapi Request object
        {
            "platforms": List of rom's ids to delete
        }

    Raises:
        HTTPException: Platform not found

    Returns:
        MessageResponse: Standard message response
    """

    platform = db_platform_handler.get_platforms(id)
    if not platform:
        error = f"Platform {platform.name} - [{platform.fs_slug}] not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    log.info(f"Deleting {platform.name} [{platform.fs_slug}] from database")
    db_platform_handler.delete_platform(id)

    return {"msg": f"{platform.name} - [{platform.fs_slug}] deleted successfully!"}
