from datetime import datetime, timezone

from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.platform import PlatformSchema
from exceptions.endpoint_exceptions import PlatformNotFoundInDatabaseException
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from fastapi import Request
from handler.auth.base_handler import Scope
from handler.database import db_platform_handler
from handler.filesystem import fs_platform_handler
from handler.metadata.igdb_handler import IGDB_PLATFORM_LIST
from handler.scan_handler import scan_platform
from logger.logger import log
from models.platform import Platform
from utils.router import APIRouter

router = APIRouter()


@protected_route(router.post, "/platforms", [Scope.PLATFORMS_WRITE])
async def add_platforms(request: Request) -> PlatformSchema:
    """Create platform endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        PlatformSchema: Just created platform
    """

    data = await request.json()
    fs_slug = data["fs_slug"]
    try:
        fs_platform_handler.add_platforms(fs_slug=fs_slug)
    except PlatformAlreadyExistsException:
        log.info(f"Detected platform: {fs_slug}")
    scanned_platform = await scan_platform(fs_slug, [fs_slug])
    return db_platform_handler.add_platform(scanned_platform)


@protected_route(router.get, "/platforms", [Scope.PLATFORMS_READ])
def get_platforms(request: Request) -> list[PlatformSchema]:
    """Get platforms endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Platform id. Defaults to None.

    Returns:
        list[PlatformSchema]: List of platforms
    """

    return db_platform_handler.get_platforms()


@protected_route(router.get, "/platforms/supported", [Scope.PLATFORMS_READ])
def get_supported_platforms(request: Request) -> list[PlatformSchema]:
    """Get list of supported platforms endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[PlatformSchema]: List of supported platforms
    """

    supported_platforms = []
    db_platforms: list[Platform] = db_platform_handler.get_platforms()
    db_platforms_map = {p.name: p.id for p in db_platforms}

    for platform in IGDB_PLATFORM_LIST:
        now = datetime.now(timezone.utc)
        sup_plat = {
            "id": -1,
            "name": platform["name"],
            "fs_slug": platform["slug"],
            "slug": platform["slug"],
            "logo_path": "",
            "roms": [],
            "rom_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        if platform["name"] in db_platforms_map:
            sup_plat["id"] = db_platforms_map[platform["name"]]

        supported_platforms.append(PlatformSchema.model_validate(sup_plat).model_dump())

    return supported_platforms


@protected_route(router.get, "/platforms/{id}", [Scope.PLATFORMS_READ])
def get_platform(request: Request, id: int) -> PlatformSchema:
    """Get platforms endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Platform id. Defaults to None.

    Returns:
        PlatformSchema: Platform
    """

    platform = db_platform_handler.get_platform(id)

    if not platform:
        raise PlatformNotFoundInDatabaseException(id)

    return platform


@protected_route(router.put, "/platforms/{id}", [Scope.PLATFORMS_WRITE])
async def update_platform(request: Request, id: int) -> PlatformSchema:
    """Update platform endpoint

    Args:
        request (Request): Fastapi Request object
        id (int): Platform id

    Returns:
        MessageResponse: Standard message response
    """
    data = await request.json()
    platform_db = db_platform_handler.get_platform(id)

    if not platform_db:
        raise PlatformNotFoundInDatabaseException(id)

    platform_db.aspect_ratio = data.get("aspect_ratio", platform_db.aspect_ratio)
    platform_db.custom_name = data.get("custom_name", platform_db.custom_name)
    platform_db = db_platform_handler.add_platform(platform_db)

    return platform_db


@protected_route(router.delete, "/platforms/{id}", [Scope.PLATFORMS_WRITE])
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

    platform = db_platform_handler.get_platform(id)

    if not platform:
        raise PlatformNotFoundInDatabaseException(id)

    log.info(f"Deleting {platform.name} [{platform.fs_slug}] from database")
    db_platform_handler.delete_platform(id)

    return {"msg": f"{platform.name} - [{platform.fs_slug}] deleted successfully!"}
