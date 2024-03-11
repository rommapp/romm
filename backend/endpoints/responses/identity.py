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
