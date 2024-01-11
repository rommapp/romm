from endpoints.responses.platform import PlatformSchema
from fastapi import APIRouter, HTTPException, Request, status
from handler import dbh
from logger.logger import log
from endpoints.responses import MessageResponse
from utils.oauth import protected_route

router = APIRouter()


@protected_route(router.get, "/platforms", ["platforms.read"])
def platforms(request: Request) -> list[PlatformSchema]:
    """Get platforms endpoint

    Args:
        request (Request): Fastapi Request object

    Returns:
        list[PlatformSchema]: All platforms in the database
    """

    return dbh.get_platforms()


@protected_route(router.delete, "/platforms/{slug}", ["platforms.write"])
def delete_platform(request: Request, slug) -> MessageResponse:
    """Detele platform from database [and filesystem]"""

    platform = dbh.get_platform(slug)
    if not platform:
        error = f"Platform {platform.name} - [{platform.fs_slug}] not found"
        log.error(error)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    log.info(f"Deleting {platform.name} [{platform.fs_slug}] from database")
    dbh.delete_platform(platform.slug)

    return {"msg": f"{platform.name} - [{platform.fs_slug}] deleted successfully!"}
