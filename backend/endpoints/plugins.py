from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from decorators.auth import protected_route
from endpoints.responses.plugin import (
    PluginFactSchema,
    PluginFactsSchema,
    PluginOptionsSchema,
    PluginSchema,
    PluginSettingsSchema,
    StorePluginSchema,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import visible_rom_or_404
from handler.database import db_rom_handler
from handler.plugin_facts import (
    PluginFactSpec,
    expand_query,
    fill_fact,
    source_url,
    still_worth_drawing,
)
from handler.plugin_handler import (
    PluginRefused,
    expand_template,
    find_facts,
    install_from_store,
    install_plugin,
    list_plugins,
    plugin_settings,
    remove_plugin,
    save_plugin_settings,
    store_plugins,
)
from handler.plugin_options import options_for
from models.user import Role
from utils.router import APIRouter

router = APIRouter(
    prefix="/plugins",
    tags=["plugins"],
)


class PluginInstallRequest(BaseModel):
    """Where a new plugin comes from: a URL to fetch, or a manifest to store."""

    url: str | None = None
    manifest: dict | None = Field(default=None, description="A plugin.json body")


def _require_admin(request: Request) -> None:
    """Refuse a caller who is not an administrator.

    A plugin installs for everyone and its settings reach everyone's browser, so
    managing one is administration rather than library work. `users.write` is
    not enough: it can be granted to someone who manages accounts.

    Args:
        request (Request): The incoming request.

    Raises:
        HTTPException: The caller is not an administrator.
    """
    if request.user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an administrator can manage plugins",
        )


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
    _require_admin(request)
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
    _require_admin(request)
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


def _rom_values(request: Request, rom_id: int) -> dict[str, str]:
    """What a manifest may interpolate about one game.

    Args:
        request: The incoming request, for the caller's view of the library.
        rom_id: The game the panel is being filled for.

    Returns:
        dict[str, str]: The placeholders, as text.

    Raises:
        HTTPException: No game with that id exists.
    """
    rom = visible_rom_or_404(request, db_rom_handler.get_rom(rom_id), rom_id)
    file_name = ""
    files = getattr(rom, "files", None) or []
    if files:
        file_name = getattr(files[0], "file_name", "") or ""
    return {
        "rom_id": str(rom.id),
        "rom_name": rom.name or "",
        "platform_slug": getattr(rom, "platform_slug", "") or "",
        "platform_name": getattr(rom, "platform_display_name", "") or "",
        "file_name": file_name,
    }


@protected_route(router.get, "/{plugin_id}/facts", [Scope.ROMS_READ])
def get_plugin_facts(
    request: Request, plugin_id: str, rom_id: int
) -> PluginFactsSchema:
    """Fill the panels a plugin declares, for one game.

    The manifest names a source and the shape of its answer; the server fetches
    it within the limits a plugin is held to. A source that fails comes back as
    a panel with the reason in `note`, so one broken lookup cannot take the page
    down with it.

    Args:
        request (Request): The incoming request.
        plugin_id (str): The id the manifest declares.
        rom_id (int): The game whose panels are being filled.

    Returns:
        PluginFactsSchema: One panel per declaration, in order.

    Raises:
        HTTPException: The plugin is not installed, or the game is not known.
    """
    plugin = _installed(plugin_id)
    specs: list[PluginFactSpec] = find_facts(plugin_id)
    if not specs:
        return PluginFactsSchema(facts=[])

    values = _rom_values(request, rom_id)
    settings = plugin_settings(plugin)

    filled: list[PluginFactSchema] = []
    for spec in specs:
        if not still_worth_drawing(spec, settings):
            continue
        url = source_url(
            expand_template(spec.url, values, settings, encode_rom=True),
            expand_query(
                {
                    name: expand_template(value, values, settings)
                    for name, value in spec.query.items()
                }
            ),
        )
        link = (
            expand_template(spec.link, values, settings, encode_rom=True)
            if spec.link
            else None
        )
        filled.append(fill_fact(plugin_id, spec, url, link))

    return PluginFactsSchema(facts=filled)


@protected_route(router.get, "/{plugin_id}/options", [Scope.ROMS_READ])
def get_plugin_options(
    request: Request,
    plugin_id: str,
    key: str,
    q: str = "",
) -> PluginOptionsSchema:
    """The choices a searchable setting offers for what the user typed.

    The list belongs to the plugin's own source, so the server asks it rather
    than shipping a catalogue to the browser. A source that cannot be reached
    comes back as an empty list and the reason, because a form that cannot be
    searched is still a form whose other fields can be saved.

    Args:
        request (Request): The incoming request.
        plugin_id (str): The id the manifest declares.
        key (str): Which setting is being filled in.
        q (str): What the user has typed so far.

    Returns:
        PluginOptionsSchema: The choices, and a note when there are none.
    """
    plugin = _installed(plugin_id)
    try:
        options, note = options_for(plugin, key, q)
    except PluginRefused as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    return PluginOptionsSchema(options=options, note=note)


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
    values = plugin_settings(plugin)
    if request.user.role != Role.ADMIN:
        # A viewer needs the values that build action URLs, not the secrets an
        # administrator typed: a password comes back blank, and blank is what a
        # form shows and never what anything saves.
        secrets = {s.key for s in plugin.settings if s.type == "password"}
        values = {
            key: (None if key in secrets else value) for key, value in values.items()
        }
    return PluginSettingsSchema(values=values)


@protected_route(router.put, "/{plugin_id}/settings", [Scope.USERS_WRITE])
def put_plugin_settings(
    request: Request, plugin_id: str, body: PluginSettingsSchema
) -> PluginSettingsSchema:
    _require_admin(request)
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
    _require_admin(request)
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
