from datetime import datetime, timezone
from typing import Annotated

from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.platform import PlatformSchema
from exceptions.endpoint_exceptions import PlatformNotFoundInDatabaseException
from exceptions.fs_exceptions import PlatformAlreadyExistsException
from fastapi import Body
from fastapi import Path as PathVar
from fastapi import Request, status
from handler.auth.constants import Scope
from handler.database import db_platform_handler
from handler.filesystem import fs_platform_handler
from handler.metadata.igdb_handler import IGDB_PLATFORM_LIST
from handler.scan_handler import scan_platform
from logger.formatter import BLUE
from logger.formatter import highlight as hl
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/platforms",
    tags=["platforms"],
)


@protected_route(
    router.post,
    "",
    [Scope.PLATFORMS_WRITE],
    status_code=status.HTTP_201_CREATED,
)
async def add_platform(
    request: Request,
    fs_slug: Annotated[str, Body(description="Platform slug.", embed=True)],
) -> PlatformSchema:
    """Create a platform."""

    try:
        fs_platform_handler.add_platforms(fs_slug=fs_slug)
    except PlatformAlreadyExistsException:
        log.info(f"Detected platform: {hl(fs_slug)}")
    scanned_platform = await scan_platform(fs_slug, [fs_slug])
    return PlatformSchema.model_validate(
        db_platform_handler.add_platform(scanned_platform)
    )


@protected_route(router.get, "", [Scope.PLATFORMS_READ])
def get_platforms(request: Request) -> list[PlatformSchema]:
    """Retrieve platforms."""

    return [
        PlatformSchema.model_validate(p) for p in db_platform_handler.get_platforms()
    ]


@protected_route(router.get, "/supported", [Scope.PLATFORMS_READ])
def get_supported_platforms(request: Request) -> list[PlatformSchema]:
    """Retrieve the list of supported platforms."""

    db_platforms = db_platform_handler.get_platforms()
    db_platforms_map = {p.name: p.id for p in db_platforms}

    now = datetime.now(timezone.utc)
    supported_platforms = []
    for platform in IGDB_PLATFORM_LIST:
        platform_id = db_platforms_map.get(platform["name"], -1)
        sup_plat = {
            "id": platform_id,
            "name": platform["name"],
            "fs_slug": platform["slug"],
            "slug": platform["slug"],
            "logo_path": "",
            "roms": [],
            "rom_count": 0,
            "created_at": now,
            "updated_at": now,
            "fs_size_bytes": 0,
            "is_unidentified": False,
            "is_identified": True,
            "missing_from_fs": False,
        }
        supported_platforms.append(PlatformSchema.model_validate(sup_plat).model_dump())

    return supported_platforms


@protected_route(
    router.get,
    "/{id}",
    [Scope.PLATFORMS_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
def get_platform(
    request: Request,
    id: Annotated[int, PathVar(description="Platform id.", ge=1)],
) -> PlatformSchema:
    """Retrieve a platform by ID."""

    platform = db_platform_handler.get_platform(id)
    if not platform:
        raise PlatformNotFoundInDatabaseException(id)
    return PlatformSchema.model_validate(platform)


@protected_route(
    router.put,
    "/{id}",
    [Scope.PLATFORMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def update_platform(
    request: Request,
    id: Annotated[int, PathVar(description="Platform id.", ge=1)],
    aspect_ratio: Annotated[str | None, Body(description="Cover aspect ratio.")] = None,
    custom_name: Annotated[
        str | None, Body(description="Custom platform name.")
    ] = None,
) -> PlatformSchema:
    """Update a platform."""

    platform_db = db_platform_handler.get_platform(id)
    if not platform_db:
        raise PlatformNotFoundInDatabaseException(id)

    if aspect_ratio is not None:
        platform_db.aspect_ratio = aspect_ratio
    if custom_name is not None:
        platform_db.custom_name = custom_name
    platform_db = db_platform_handler.add_platform(platform_db)

    return PlatformSchema.model_validate(platform_db)


@protected_route(
    router.delete,
    "/{id}",
    [Scope.PLATFORMS_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def delete_platform(
    request: Request,
    id: Annotated[int, PathVar(description="Platform id.", ge=1)],
) -> MessageResponse:
    """Delete a platform."""

    platform = db_platform_handler.get_platform(id)
    if not platform:
        raise PlatformNotFoundInDatabaseException(id)

    log.info(
        f"Deleting {hl(platform.name,  color=BLUE)} [{hl(platform.fs_slug)}] from database"
    )
    db_platform_handler.delete_platform(id)

    return {"msg": f"{platform.name} - [{platform.fs_slug}] deleted successfully!"}
