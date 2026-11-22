from decorators.auth import protected_route
from fastapi import Request
from handler.auth.constants import Scope
from handler.plugin_handler import list_plugins
from utils.router import APIRouter

from endpoints.responses.plugin import PluginSchema

router = APIRouter(
    prefix="/plugins",
    tags=["plugins"],
)


@protected_route(router.get, "", [Scope.ROMS_READ])
def get_plugins(request: Request) -> list[PluginSchema]:
    """Every plugin installed beside the library, and the actions it adds.

    Args:
        request (Request): The incoming request.

    Returns:
        list[PluginSchema]: The installed plugins, alphabetically by name.
    """
    return list_plugins()
