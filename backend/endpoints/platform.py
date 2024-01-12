from config.config_manager import config_manager as cm
from decorators.oauth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.platform import PlatformSchema
from fastapi import APIRouter, HTTPException, Request, status
from handler import dbh
from logger.logger import log

router = APIRouter()


@protected_route(router.get, "/platforms", ["platforms.read"])
def get_platforms(request: Request) -> list[PlatformSchema]:
    """Get platforms endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[PlatformSchema]: All platforms in the database
    """

    return dbh.get_platform()


@protected_route(router.get, "/platforms/{id}", ["platforms.read"])
def get_platforms(request: Request, id: int = None) -> PlatformSchema:
    """Get platform endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        PlatformSchema: All platforms in the database
    """

    return dbh.get_platform(id)


@protected_route(router.delete, "/platforms/{id}", ["platforms.write"])
def delete_platforms(request: Request, id: int) -> MessageResponse:
    """Detele platform from database [and filesystem]"""

    platform = dbh.get_platform(id)
    if not platform:
        error = f"Platform {platform.name} - [{platform.fs_slug}] not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    log.info(f"Deleting {platform.name} [{platform.fs_slug}] from database")
    dbh.delete_platform(platform.id)

    return {"msg": f"{platform.name} - [{platform.fs_slug}] deleted successfully!"}


@protected_route(router.put, "/config/system/platforms", ["platforms.write"])
async def add_platform_binding(request: Request) -> MessageResponse:
    """Add platform binding to the configuration"""

    data = await request.form()

    fs_slug = data.get("fs_slug")
    slug = data.get("slug")

    cm.add_binding(fs_slug, slug)

    return {"msg": f"{fs_slug} binded to: {slug} successfully!"}


@protected_route(router.patch, "/config/system/platforms", ["platforms.write"])
async def delete_platform_binding(request: Request) -> MessageResponse:
    """Delete platform binding from the configuration"""

    data = await request.form()

    fs_slug = data.get("fs_slug")

    cm.remove_binding(fs_slug)

    return {"msg": f"{fs_slug} bind removed successfully!"}
