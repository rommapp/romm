from fastapi import HTTPException, Request, status

from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from endpoints.responses.config import ConfigResponse
from exceptions.config_exceptions import ConfigNotWritableException
from handler.auth.constants import Scope
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/config",
    tags=["config"],
)


@router.get("")
def get_config() -> ConfigResponse:
    """Get config endpoint

    Returns:
        ConfigResponse: RomM's configuration
    """

    cfg = cm.get_config()
    return ConfigResponse(
        CONFIG_FILE_MOUNTED=cfg.CONFIG_FILE_MOUNTED,
        CONFIG_FILE_WRITABLE=cfg.CONFIG_FILE_WRITABLE,
        EXCLUDED_PLATFORMS=cfg.EXCLUDED_PLATFORMS,
        EXCLUDED_SINGLE_EXT=cfg.EXCLUDED_SINGLE_EXT,
        EXCLUDED_SINGLE_FILES=cfg.EXCLUDED_SINGLE_FILES,
        EXCLUDED_MULTI_FILES=cfg.EXCLUDED_MULTI_FILES,
        EXCLUDED_MULTI_PARTS_EXT=cfg.EXCLUDED_MULTI_PARTS_EXT,
        EXCLUDED_MULTI_PARTS_FILES=cfg.EXCLUDED_MULTI_PARTS_FILES,
        PLATFORMS_BINDING=cfg.PLATFORMS_BINDING,
        PLATFORMS_VERSIONS=cfg.PLATFORMS_VERSIONS,
        EJS_DEBUG=cfg.EJS_DEBUG,
        EJS_CACHE_LIMIT=cfg.EJS_CACHE_LIMIT,
        EJS_CONTROLS=cfg.EJS_CONTROLS,
        EJS_SETTINGS=cfg.EJS_SETTINGS,
        SCAN_METADATA_PRIORITY=cfg.SCAN_METADATA_PRIORITY,
        SCAN_ARTWORK_PRIORITY=cfg.SCAN_ARTWORK_PRIORITY,
        SCAN_REGION_PRIORITY=cfg.SCAN_REGION_PRIORITY,
        SCAN_LANGUAGE_PRIORITY=cfg.SCAN_LANGUAGE_PRIORITY,
    )


@protected_route(router.post, "/system/platforms", [Scope.PLATFORMS_WRITE])
async def add_platform_binding(request: Request) -> None:
    """Add platform binding to the configuration"""

    data = await request.json()
    fs_slug = data["fs_slug"]
    slug = data["slug"]

    try:
        cm.add_platform_binding(fs_slug, slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.delete, "/system/platforms/{fs_slug}", [Scope.PLATFORMS_WRITE])
async def delete_platform_binding(request: Request, fs_slug: str) -> None:
    """Delete platform binding from the configuration"""

    try:
        cm.remove_platform_binding(fs_slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.post, "/system/versions", [Scope.PLATFORMS_WRITE])
async def add_platform_version(request: Request) -> None:
    """Add platform version to the configuration"""

    data = await request.json()
    fs_slug = data["fs_slug"]
    slug = data["slug"]

    try:
        cm.add_platform_version(fs_slug, slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.delete, "/system/versions/{fs_slug}", [Scope.PLATFORMS_WRITE])
async def delete_platform_version(request: Request, fs_slug: str) -> None:
    """Delete platform version from the configuration"""

    try:
        cm.remove_platform_version(fs_slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.post, "/exclude", [Scope.PLATFORMS_WRITE])
async def add_exclusion(request: Request) -> None:
    """Add platform exclusion to the configuration"""

    data = await request.json()
    exclusion_value = data["exclusion_value"]
    exclusion_type = data["exclusion_type"]
    try:
        cm.add_exclusion(exclusion_type, exclusion_value)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(
    router.delete,
    "/exclude/{exclusion_type}/{exclusion_value}",
    [Scope.PLATFORMS_WRITE],
)
async def delete_exclusion(
    request: Request, exclusion_type: str, exclusion_value: str
) -> None:
    """Delete platform binding from the configuration"""

    try:
        cm.remove_exclusion(exclusion_type, exclusion_value)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc
