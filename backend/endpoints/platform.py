from datetime import datetime, timezone

from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.platform import PlatformSchema
from exceptions.endpoint_exceptions import PlatformNotFoundInDatabaseException
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from fastapi import Request
from handler.auth.constants import Scope
from handler.database import db_platform_handler
from handler.filesystem import fs_platform_handler
from handler.metadata.base_hander import UNIVERSAL_PLATFORM_SLUGS
from handler.metadata.igdb_handler import SLUG_TO_IGDB_PLATFORM
from handler.metadata.moby_handler import SLUG_TO_MOBY_PLATFORM
from handler.metadata.ss_handler import SLUG_TO_SS_PLATFORM
from handler.scan_handler import scan_platform
from logger.logger import log
from models.platform import DEFAULT_COVER_ASPECT_RATIO, Platform
from utils.router import APIRouter

router = APIRouter(
    prefix="/platforms",
    tags=["platforms"],
)


@protected_route(router.post, "", [Scope.PLATFORMS_WRITE])
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
    return PlatformSchema.model_validate(
        db_platform_handler.add_platform(scanned_platform)
    )


@protected_route(router.get, "", [Scope.PLATFORMS_READ])
def get_platforms(request: Request) -> list[PlatformSchema]:
    """Get platforms endpoint

    Args:
        request (Request): Fastapi Request object
        id (int, optional): Platform id. Defaults to None.

    Returns:
        list[PlatformSchema]: List of platforms
    """

    return [
        PlatformSchema.model_validate(p) for p in db_platform_handler.get_platforms()
    ]


@protected_route(router.get, "/supported", [Scope.PLATFORMS_READ])
def get_supported_platforms(request: Request) -> list[PlatformSchema]:
    """Get list of supported platforms endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[PlatformSchema]: List of supported platforms
    """

    supported_platforms = []
    db_platforms = db_platform_handler.get_platforms()
    db_platforms_map = {p.slug: p for p in db_platforms}

    for slug in UNIVERSAL_PLATFORM_SLUGS:
        now = datetime.now(timezone.utc)

        db_platform = db_platforms_map.get(slug, None)
        igdb_platform = SLUG_TO_IGDB_PLATFORM.get(slug, None)
        moby_platform = SLUG_TO_MOBY_PLATFORM.get(slug, None)
        ss_platform = SLUG_TO_SS_PLATFORM.get(slug, None)

        common_propeties = {
            "id": -1,
            "name": slug.capitalize(),
            "fs_slug": slug,
            "slug": slug,
            "roms": [],
            "rom_count": 0,
            "aspect_ratio": DEFAULT_COVER_ASPECT_RATIO,
            "created_at": now,
            "updated_at": now,
        }

        if db_platform:
            supported_platforms.append(
                PlatformSchema.model_validate(db_platform).model_dump()
            )
            continue

        if ss_platform:
            common_propeties.update(
                {
                    "name": ss_platform["name"],
                    "ss_id": ss_platform["id"],
                }
            )

        if moby_platform:
            common_propeties.update(
                {
                    "name": moby_platform["name"],
                    "moby_id": moby_platform["id"],
                }
            )

        if igdb_platform:
            common_propeties.update(
                {
                    "name": igdb_platform["name"],
                    "igdb_id": igdb_platform["id"],
                    "category": igdb_platform["category"],
                    "generation": igdb_platform["generation"],
                    "family_name": igdb_platform["family_name"],
                    "family_slug": igdb_platform["family_slug"],
                    "url_logo": igdb_platform["url_logo"],
                }
            )

        platform = Platform(**common_propeties)
        supported_platforms.append(PlatformSchema.model_validate(platform).model_dump())

    return supported_platforms


@protected_route(router.get, "/{id}", [Scope.PLATFORMS_READ])
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

    return PlatformSchema.model_validate(platform)


@protected_route(router.put, "/{id}", [Scope.PLATFORMS_WRITE])
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

    return PlatformSchema.model_validate(platform_db)


@protected_route(router.delete, "/{id}", [Scope.PLATFORMS_WRITE])
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
