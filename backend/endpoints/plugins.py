from decorators.auth import protected_route
from fastapi import HTTPException, Request, status
from handler.auth.constants import Scope
from handler.plugin_handler import (
    PluginRefused,
    install_plugin,
    list_plugins,
    remove_plugin,
)
from pydantic import BaseModel, Field
from utils.router import APIRouter

from endpoints.responses.plugin import PluginSchema

router = APIRouter(
    prefix="/plugins",
    tags=["plugins"],
)


class PluginInstallRequest(BaseModel):
    """Where a new plugin comes from: a URL to fetch, or a manifest to store."""

    url: str | None = None
    manifest: dict | None = Field(default=None, description="A plugin.json body")


@protected_route(router.get, "", [Scope.ROMS_READ])
def get_plugins(request: Request) -> list[PluginSchema]:
    """Every plugin installed beside the library, and the actions it adds.

    Args:
        request (Request): The incoming request.

    Returns:
        list[PluginSchema]: The installed plugins, alphabetically by name.
    """
    return list_plugins()


@protected_route(router.post, "", [Scope.USERS_WRITE])
def add_plugin(request: Request, body: PluginInstallRequest) -> PluginSchema:
    """Install a plugin from a URL, or from a manifest the caller sends.

    Args:
        request (Request): The incoming request.
        body (PluginInstallRequest): Where the manifest comes from.

    Returns:
        PluginSchema: The plugin, as the UI will read it.

    Raises:
        HTTPException: The source is not a usable manifest, or one with that
            id is already installed.
    """
    try:
        return install_plugin(manifest=body.manifest, url=body.url)
    except PluginRefused as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@protected_route(router.delete, "/{plugin_id}", [Scope.USERS_WRITE])
def delete_plugin(request: Request, plugin_id: str) -> None:
    """Remove an installed plugin.

    Args:
        request (Request): The incoming request.
        plugin_id (str): The id the manifest declares.

    Raises:
        HTTPException: No such plugin, or its folder cannot be removed.
    """
    try:
        remove_plugin(plugin_id)
    except PluginRefused as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
