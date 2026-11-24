from typing import Any, Literal

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
PluginSettingType = Literal[
    "text",
    "url",
    "number",
    "boolean",
    "select",
    "password",
    "search",  # a select whose choices come from the plugin's own source
    "groups",  # a list the user builds, each entry holding its own fields
]


class PluginOptionSchema(BaseModel):
    """One choice a searchable field offers."""

    value: str
    label: str


class PluginOptionsSchema(BaseModel):
    """The choices a search found.

    An error is said in `note` and comes with an empty list: a source that is
    down is not a reason to close the form.
    """

    options: list[PluginOptionSchema] = Field(default_factory=list)
    note: str | None = None


class PluginSettingOptionSchema(BaseModel):
    """One choice of a `select` field."""

    value: str
    label: str


class PluginOptionSourceSchema(BaseModel):
    """Where a searchable field gets its choices.

    The list is served by the plugin's own source, not by RomM: RomM only asks
    it and shows what comes back.
    """

    # The address asked for every search, with `{query}` standing in for the
    # text the user typed.
    url: str
    # Query parameters to send, of which one usually carries `{query}`.
    query: dict[str, str] = Field(default_factory=dict)
    # Dotted paths into the reply: where the list is, and what names an entry.
    items: str
    value: str
    label: str
    # How many a search may bring back.
    limit: int = 20


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
    # `search`: whose API answers the search.
    source: PluginOptionSourceSchema | None = None
    # `groups`: the fields one entry of the list holds.
    fields: list[PluginSettingSchema] = Field(default_factory=list)
    # `groups`: how many entries the list may hold.
    max_items: int = 8


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
    """A plugin's saved values, keyed by the manifest's setting keys.

    A value is whatever the field holds, which for a `groups` field is a list of
    entries. Narrowing this to scalars would refuse the whole request before the
    manifest got a look at it.
    """

    values: dict[str, Any] = Field(default_factory=dict)


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
