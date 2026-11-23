from decorators.auth import protected_route
from fastapi import HTTPException, Request, status
from handler.auth.constants import Scope
from handler.plugin_handler import (
    PluginRefused,
    install_from_store,
    install_plugin,
    list_plugins,
    plugin_settings,
    remove_plugin,
    save_plugin_settings,
    store_plugins,
)
from pydantic import BaseModel, Field
from utils.router import APIRouter

from endpoints.responses.plugin import (
    PluginSchema,
    PluginSettingsSchema,
    StorePluginSchema,
)

router = APIRouter(
    prefix="/plugins",
    tags=["plugins"],
)


class PluginInstallRequest(BaseModel):
    """Where a new plugin comes from: a URL to fetch, or a manifest to store."""

    url: str | None = None
    manifest: dict | None = Field(default=None, description="A plugin.json body")


def _installed(plugin_id: str) -> PluginSchema:
    """The installed plugin with this id, or a 404.

    Args:
        plugin_id: The id the manifest declares.

    Returns:
        PluginSchema: The plugin as the shelf read it.

    Raises:
        HTTPException: No plugin with that id is installed.
    """
    for plugin in list_plugins():
        if plugin.id == plugin_id:
            return plugin
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"{plugin_id} is not installed"
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


@protected_route(router.get, "/store", [Scope.ROMS_READ])
def get_store(request: Request) -> list[StorePluginSchema]:
    """The curated index, so the UI can offer what a repository lists.

    Args:
        request (Request): The incoming request.

    Returns:
        list[StorePluginSchema]: The plugins the store offers.

    Raises:
        HTTPException: The index cannot be fetched or read.
    """
    try:
        return store_plugins()
    except PluginRefused as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc


@protected_route(router.post, "/store/{plugin_id}", [Scope.USERS_WRITE])
def install_store_plugin(request: Request, plugin_id: str) -> PluginSchema:
    """Install a plugin the store lists.

    Args:
        request (Request): The incoming request.
        plugin_id (str): The id the store lists it under.

    Returns:
        PluginSchema: The installed plugin.

    Raises:
        HTTPException: The store has no such plugin, or it won't install.
    """
    try:
        return install_from_store(plugin_id)
    except PluginRefused as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@protected_route(router.get, "/{plugin_id}/settings", [Scope.ROMS_READ])
def get_plugin_settings(request: Request, plugin_id: str) -> PluginSettingsSchema:
    """A plugin's current values, with the manifest's defaults filled in.

    Args:
        request (Request): The incoming request.
        plugin_id (str): The id the manifest declares.

    Returns:
        PluginSettingsSchema: One value per setting the manifest declares.
    """
    plugin = _installed(plugin_id)
    return PluginSettingsSchema(values=plugin_settings(plugin))


@protected_route(router.put, "/{plugin_id}/settings", [Scope.USERS_WRITE])
def put_plugin_settings(
    request: Request, plugin_id: str, body: PluginSettingsSchema
) -> PluginSettingsSchema:
    """Save a plugin's settings, validated against its manifest.

    Args:
        request (Request): The incoming request.
        plugin_id (str): The id the manifest declares.
        body (PluginSettingsSchema): The values the form sent.

    Returns:
        PluginSettingsSchema: The values as they were stored.

    Raises:
        HTTPException: A key the manifest doesn't declare, or a value of the
            wrong type.
    """
    plugin = _installed(plugin_id)
    try:
        stored = save_plugin_settings(plugin, body.values)
    except PluginRefused as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return PluginSettingsSchema(values=stored)


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
