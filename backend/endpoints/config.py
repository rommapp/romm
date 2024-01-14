from config.config_manager import config_manager as cm
from decorators.auth import protected_route
from endpoints.responses import MessageResponse
from endpoints.responses.config import ConfigResponse
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/config")
def get_config() -> ConfigResponse:
    """Get config endpoint

    Returns:
        ConfigResponse: RomM's configuration
    """

    cm.read_config()
    return cm.config.__dict__


@protected_route(router.post, "/config/system/platforms", ["platforms.write"])
async def add_platform_binding(request: Request) -> MessageResponse:
    """Add platform binding to the configuration"""

    data = await request.form()
    fs_slug = data.get("fs_slug")
    slug = data.get("slug")
    cm.add_binding(fs_slug, slug)

    return {"msg": f"{fs_slug} binded to: {slug} successfully!"}


@protected_route(router.put, "/config/system/platforms", ["platforms.write"])
async def delete_platform_binding(request: Request) -> MessageResponse:
    """Delete platform binding from the configuration"""

    data = await request.form()
    fs_slug = data.get("fs_slug")
    cm.remove_binding(fs_slug)

    return {"msg": f"{fs_slug} bind removed successfully!"}
