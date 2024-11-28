from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.config import ConfigResponse
from exceptions.config_exceptions import (
    ConfigNotReadableException,
    ConfigNotWritableException,
)
from fastapi import HTTPException, Request, status
from handler.auth.base_handler import Scope
from logger.logger import log
from utils.router import APIRouter

router = APIRouter()


@router.get("/config")
def get_config() -> ConfigResponse:
    """Get config endpoint

    Returns:
        ConfigResponse: RomM's configuration
    """

    try:
        cfg = cm.get_config()
        return ConfigResponse(
            EXCLUDED_PLATFORMS=cfg.EXCLUDED_PLATFORMS,
            EXCLUDED_SINGLE_EXT=cfg.EXCLUDED_SINGLE_EXT,
            EXCLUDED_SINGLE_FILES=cfg.EXCLUDED_SINGLE_FILES,
            EXCLUDED_MULTI_FILES=cfg.EXCLUDED_MULTI_FILES,
            EXCLUDED_MULTI_PARTS_EXT=cfg.EXCLUDED_MULTI_PARTS_EXT,
            EXCLUDED_MULTI_PARTS_FILES=cfg.EXCLUDED_MULTI_PARTS_FILES,
            PLATFORMS_BINDING=cfg.PLATFORMS_BINDING,
            PLATFORMS_VERSIONS=cfg.PLATFORMS_VERSIONS,
        )
    except ConfigNotReadableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


@protected_route(router.post, "/config/system/platforms", [Scope.PLATFORMS_WRITE])
async def add_platform_binding(request: Request) -> MessageResponse:
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

    return {"msg": f"{fs_slug} binded to: {slug} successfully!"}


@protected_route(
    router.delete, "/config/system/platforms/{fs_slug}", [Scope.PLATFORMS_WRITE]
)
async def delete_platform_binding(request: Request, fs_slug: str) -> MessageResponse:
    """Delete platform binding from the configuration"""

    try:
        cm.remove_platform_binding(fs_slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc

    return {"msg": f"{fs_slug} bind removed successfully!"}


@protected_route(router.post, "/config/system/versions", [Scope.PLATFORMS_WRITE])
async def add_platform_version(request: Request) -> MessageResponse:
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

    return {"msg": f"Added {fs_slug} as version of: {slug} successfully!"}


@protected_route(
    router.delete, "/config/system/versions/{fs_slug}", [Scope.PLATFORMS_WRITE]
)
async def delete_platform_version(request: Request, fs_slug: str) -> MessageResponse:
    """Delete platform version from the configuration"""

    try:
        cm.remove_platform_version(fs_slug)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc

    return {"msg": f"{fs_slug} version removed successfully!"}


@protected_route(router.post, "/config/exclude", [Scope.PLATFORMS_WRITE])
async def add_exclusion(request: Request) -> MessageResponse:
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

    return {
        "msg": f"Exclusion {exclusion_value} added to {exclusion_type} successfully!"
    }


@protected_route(
    router.delete,
    "/config/exclude/{exclusion_type}/{exclusion_value}",
    [Scope.PLATFORMS_WRITE],
)
async def delete_exclusion(
    request: Request, exclusion_type: str, exclusion_value: str
) -> MessageResponse:
    """Delete platform binding from the configuration"""

    try:
        cm.remove_exclusion(exclusion_type, exclusion_value)
    except ConfigNotWritableException as exc:
        log.critical(exc.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc

    return {
        "msg": f"Exclusion {exclusion_value} removed from {exclusion_type} successfully!"
    }
