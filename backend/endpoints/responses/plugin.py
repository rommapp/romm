from typing import Literal

from pydantic import BaseModel, Field

# Where an action is drawn. Every slot is one place in the UI that renders
# whatever plugins declare for it, so a new surface is a new value here and a
# mount of the same renderer rather than a new shape.
PluginSlot = Literal[
    "game.details",  # the action row on a game
    "game.play",  # a way to start a game, inside the Play menu
    "app.nav",  # an entry in the app's navigation
    "settings.page",  # a row on Settings, Plugins
]

# What a plugin asks its user for. The manifest describes the fields; the values
# live beside it in the plugin's folder and reach an action's URL through
# {setting.<key>}, so a plugin stays declarative: it never runs, it is told.
PluginSettingType = Literal["text", "url", "number", "boolean", "select", "password"]


class PluginSettingOptionSchema(BaseModel):
    """One choice of a `select` field."""

    value: str
    label: str


class PluginSettingSchema(BaseModel):
    """One field a plugin's settings form shows."""

    key: str
    label: str
    type: PluginSettingType = "text"
    default: str | int | float | bool | None = None
    help: str | None = None
    placeholder: str | None = None
    options: list[PluginSettingOptionSchema] = Field(default_factory=list)
    min: float | None = None
    max: float | None = None
    required: bool = False


class PluginActionSchema(BaseModel):
    """One thing a plugin adds to the UI, with its URL template unexpanded."""

    id: str
    label: str
    icon: str | None = None
    image: str | None = None
    url: str
    open: Literal["new-tab", "same-tab"] = "new-tab"
    slot: PluginSlot = "game.details"
    # Empty means every platform; the UI compares these against the game's slug.
    platforms: list[str] = Field(default_factory=list)
    # Key of a boolean setting that must be on for the action to be drawn.
    enabled_by: str | None = None


class PluginSchema(BaseModel):
    """A plugin manifest, as the UI reads it."""

    id: str
    name: str
    version: str
    description: str | None = None
    author: str | None = None
    homepage: str | None = None
    actions: list[PluginActionSchema] = Field(default_factory=list)
    settings: list[PluginSettingSchema] = Field(default_factory=list)


class PluginSettingsSchema(BaseModel):
    """A plugin's saved values, keyed by the manifest's setting keys."""

    values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class StorePluginSchema(BaseModel):
    """One entry of the plugin store's index: enough to install it."""

    id: str
    name: str
    version: str = "0.0.0"
    description: str | None = None
    author: str | None = None
    homepage: str | None = None
    # Where the store keeps this plugin's plugin.json.
    manifest_url: str
    tags: list[str] = Field(default_factory=list)
