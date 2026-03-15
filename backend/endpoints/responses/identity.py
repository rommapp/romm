from typing import NotRequired, TypedDict, get_type_hints

from pydantic import ConfigDict

from handler.metadata.ra_handler import RAUserProgression
from models.user import Role

from .base import BaseModel, UTCDatetime

RAProgression = TypedDict(  # type: ignore[misc]
    "RAProgression",
    {k: NotRequired[v] for k, v in get_type_hints(RAUserProgression).items()},  # type: ignore[misc]
    total=False,
)


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    enabled: bool
    role: Role
    oauth_scopes: list[str]
    avatar_path: str
    last_login: UTCDatetime | None
    last_active: UTCDatetime | None
    ra_username: str | None = None
    ra_progression: RAProgression | None = None
    ui_settings: dict | None = None

    created_at: UTCDatetime
    updated_at: UTCDatetime


class InviteLinkSchema(BaseModel):
    token: str
