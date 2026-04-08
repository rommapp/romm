from typing import NotRequired, TypedDict, get_type_hints

from pydantic import ConfigDict
from starlette.requests import Request

from handler.metadata.ra_handler import RAUserProgression
from models.user import Role, User

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
    current_device_id: str | None = None

    created_at: UTCDatetime
    updated_at: UTCDatetime

    @classmethod
    def from_orm_with_request(
        cls, db_user: User | None, request: Request
    ) -> "UserSchema | None":
        if not db_user:
            return None

        schema = cls.model_validate(db_user)
        schema.current_device_id = request.session.get("device_id")
        return schema


class InviteLinkSchema(BaseModel):
    token: str
