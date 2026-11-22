from typing import Literal

from pydantic import BaseModel, Field


class PluginActionSchema(BaseModel):
    """One button a plugin adds to a game, with its URL template unexpanded."""

    id: str
    label: str
    icon: str | None = None
    url: str
    open: Literal["new-tab", "same-tab"] = "new-tab"


class PluginSchema(BaseModel):
    """A plugin manifest, as the UI reads it."""

    id: str
    name: str
    version: str
    description: str | None = None
    author: str | None = None
    homepage: str | None = None
    actions: list[PluginActionSchema] = Field(default_factory=list)
