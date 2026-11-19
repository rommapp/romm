from typing import Any, NotRequired, TypedDict, get_type_hints

from pydantic import ConfigDict
from starlette.requests import Request

from handler.metadata.ra_handler import RAUserProgression
from models.user import Role, User
from utils.auth import current_device_id
from utils.urls import get_public_base_url

from .base import BaseModel, UTCDatetime

RAProgression = TypedDict(  # type: ignore[misc]
    "RAProgression",
    {k: NotRequired[v] for k, v in get_type_hints(RAUserProgression).items()},
    total=False,
)


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    """The internal ID of the user."""
    username: str
    """The username."""
    email: str | None
    """The email address."""
    enabled: bool
    """Whether the user can sign in."""
    role: Role
    """The role of the user: `admin` or `user`."""
    permission_group_id: int | None = None
    """The ID of the user's permission group."""
    oauth_scopes: list[str]
    """The OAuth scopes of the user."""
    has_password: bool
    """Whether the user has a password."""
    email_managed_by_oidc: bool
    """Whether the email address comes from the OIDC provider."""
    avatar_path: str
    """The path to the user's avatar."""
    last_login: UTCDatetime | None
    """When the user last signed in."""
    last_active: UTCDatetime | None
    """When the user was last active."""
    ra_username: str | None = None
    """The user's RetroAchievements username."""
    ra_progression: RAProgression | None = None
    """The user's RetroAchievements progress."""
    ui_settings: dict[str, Any] | None = None
    """The user's interface settings."""
    current_device_id: str | None = None
    """The ID of the device making the request, when there is one."""

    created_at: UTCDatetime
    """When the user was created."""
    updated_at: UTCDatetime
    """When the user last changed."""

    @classmethod
    def from_orm_with_request(
        cls, db_user: User | None, request: Request
    ) -> "UserSchema | None":
        if not db_user:
            return None

        schema = cls.model_validate(db_user)
        schema.current_device_id = current_device_id(request)
        return schema


class InviteLinkSchema(BaseModel):
    token: str
    url: str | None = None

    @classmethod
    def from_token(cls, token: str) -> "InviteLinkSchema":
        base_url = get_public_base_url()
        return cls(
            token=token,
            url=f"{base_url}/register?token={token}" if base_url else None,
        )
