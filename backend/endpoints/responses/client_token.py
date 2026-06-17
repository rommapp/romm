from pydantic import ConfigDict

from .base import BaseModel, UTCDatetime


class ClientTokenSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scopes: list[str]
    expires_at: UTCDatetime | None
    last_used_at: UTCDatetime | None
    created_at: UTCDatetime
    user_id: int


class ClientTokenCreateSchema(ClientTokenSchema):
    raw_token: str


class ClientTokenAdminSchema(ClientTokenSchema):
    username: str
    user_avatar_path: str
    user_updated_at: UTCDatetime


class ClientTokenPairSchema(BaseModel):
    code: str
    expires_in: int
