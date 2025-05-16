from datetime import datetime
from typing import NotRequired, TypedDict, get_type_hints

from handler.metadata.ra_handler import RAUserProgression
from models.user import Role

from .base import BaseModel

RAProgression = TypedDict(  # type: ignore[misc]
    "RAProgression",
    dict((k, NotRequired[v]) for k, v in get_type_hints(RAUserProgression).items()),
    total=False,
)


class UserSchema(BaseModel):
    id: int
    username: str
    email: str | None
    enabled: bool
    role: Role
    oauth_scopes: list[str]
    avatar_path: str
    last_login: datetime | None
    last_active: datetime | None
    ra_username: str | None = None
    ra_progression: RAProgression | None = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InviteLinkSchema(BaseModel):
    token: str
