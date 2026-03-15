from datetime import datetime

from pydantic import ConfigDict

from .base import BaseModel


class ClientTokenSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scopes: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    user_id: int


class ClientTokenCreateSchema(ClientTokenSchema):
    raw_token: str


class ClientTokenAdminSchema(ClientTokenSchema):
    username: str


class ClientTokenPairSchema(BaseModel):
    code: str
    expires_in: int
