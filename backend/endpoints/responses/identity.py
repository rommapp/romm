from typing import Optional

from fastapi import File, UploadFile
from models.user import Role
from pydantic import BaseModel


class UserSchema(BaseModel):
    id: int
    username: str
    enabled: bool
    role: Role
    oauth_scopes: list[str]
    avatar_path: str

    class Config:
        from_attributes = True


class UserUpdateForm:
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        role: Optional[str] = None,
        enabled: Optional[bool] = None,
        avatar: Optional[UploadFile] = File(None),
    ):
        self.username = username
        self.password = password
        self.role = role
        self.enabled = enabled
        self.avatar = avatar
