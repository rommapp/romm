from datetime import datetime

from models.user import Role
from pydantic import BaseModel


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

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
