from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.config import ConfigResponse
from exceptions.config_exceptions import (
    ConfigNotReadableException,
    ConfigNotWritableException,
)
from fastapi import APIRouter, HTTPException, Request, status
from logger.logger import log

router = APIRouter()


@router.get("/config")
def get_config() -> ConfigResponse:
    """Get config endpoint

    Returns:
        ConfigResponse: RomM's configuration
    """

    try:
        cm.read_config()
    except ConfigNotReadableException as e:
        log.critical(e.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message
        )

    return cm.config.__dict__


@protected_route(router.post, "/config/system/platforms", ["platforms.write"])
async def add_platform_binding(request: Request) -> MessageResponse:
    """Add platform binding to the configuration"""

    data = await request.json()
    fs_slug = data["fs_slug"]
    slug = data["slug"]

    try:
        cm.add_binding(fs_slug, slug)
    except ConfigNotWritableException as e:
        log.critical(e.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message
        )

    return {"msg": f"{fs_slug} binded to: {slug} successfully!"}


@protected_route(
    router.delete, "/config/system/platforms/{fs_slug}", ["platforms.write"]
)
async def delete_platform_binding(request: Request, fs_slug: str) -> MessageResponse:
    """Delete platform binding from the configuration"""

    try:
        cm.remove_binding(fs_slug)
    except ConfigNotWritableException as e:
        log.critical(e.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message
        )

    return {"msg": f"{fs_slug} bind removed successfully!"}


@protected_route(router.post, "/config/system/versions", ["platforms.write"])
async def add_platform_version(request: Request) -> MessageResponse:
    """Add platform version to the configuration"""

    data = await request.json()
    fs_slug = data["fs_slug"]
    slug = data["slug"]

    try:
        cm.add_version(fs_slug, slug)
    except ConfigNotWritableException as e:
        log.critical(e.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message
        )

    return {"msg": f"Added {fs_slug} as version of: {slug} successfully!"}


@protected_route(
    router.delete, "/config/system/versions/{fs_slug}", ["platforms.write"]
)
async def delete_platform_version(request: Request, fs_slug: str) -> MessageResponse:
    """Delete platform version from the configuration"""

    try:
        cm.remove_version(fs_slug)
    except ConfigNotWritableException as e:
        log.critical(e.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=e.message
        )

    return {"msg": f"{fs_slug} version removed successfully!"}


# @protected_route(router.post, "/config/exclude", ["platforms.write"])
# async def add_exclusion(request: Request) -> MessageResponse:
#     """Add platform binding to the configuration"""

#     data = await request.json()
#     exclude = data['exclude']
#     exclusion = data['exclusion']
#     cm.add_exclusion(exclude, exclusion)

#     return {"msg": f"Exclusion {exclusion} added to {exclude} successfully!"}


# @protected_route(router.delete, "/config/exclude", ["platforms.write"])
# async def delete_exclusion(request: Request) -> MessageResponse:
#     """Delete platform binding from the configuration"""

#     data = await request.json()
#     exclude = data['exclude']
#     exclusion = data['exclusion']
#     cm.remove_exclusion(exclude, exclusion)

#     return {"msg": f"Exclusion {exclusion} removed from {exclude} successfully!"}
