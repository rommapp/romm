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


class PluginFactSummarySchema(BaseModel):
    """A panel a plugin fills by asking its own server for data.

    The UI needs to know that a panel exists, where it belongs, and which action
    it explains; what it fetches, and how, stays on the server, so a manifest's
    request cannot be read back out of the plugin list.
    """

    id: str
    label: str
    slot: PluginSlot = "game.details"
    # The action this panel is about, when the manifest ties them together. A
    # button that opens a report can then show what the report says on hover.
    action: str | None = None


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
    facts: list[PluginFactSummarySchema] = Field(default_factory=list)


class PluginSettingsSchema(BaseModel):
    """A plugin's saved values, keyed by the manifest's setting keys."""

    values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class PluginFactGroupSchema(BaseModel):
    """One thing the reports were grouped by, and how they rated."""

    key: str
    counts: dict[str, int] = Field(default_factory=dict)
    total: int = 0


class PluginFactSchema(BaseModel):
    """A plugin's panel, filled with what its source answered.

    `note` carries why a panel is empty: a title nobody has reported on, a
    source that timed out, a manifest whose paths no longer match. It is said
    rather than raised, because a compatibility lookup failing is not a reason
    to break the page it sits on.
    """

    id: str
    label: str
    slot: PluginSlot = "game.details"
    link: str | None = None
    groups: list[PluginFactGroupSchema] = Field(default_factory=list)
    total: int = 0
    note: str | None = None


class PluginFactsSchema(BaseModel):
    """Every panel one plugin fills for one game."""

    facts: list[PluginFactSchema] = Field(default_factory=list)


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
