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


class PluginSchema(BaseModel):
    """A plugin manifest, as the UI reads it."""

    id: str
    name: str
    version: str
    description: str | None = None
    author: str | None = None
    homepage: str | None = None
    actions: list[PluginActionSchema] = Field(default_factory=list)
