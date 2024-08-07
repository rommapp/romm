from datetime import datetime

from models.collection import Collection
from pydantic import BaseModel


class CollectionSchema(BaseModel):
    id: int
    name: str
    description: str
    path_cover_l: str | None
    path_cover_s: str | None
    has_cover: bool
    url_cover: str
    roms: set[int]
    rom_count: int
    user_id: int
    user__username: str
    is_public: bool

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def for_user(
        cls, user_id: int, collections: list["Collection"]
    ) -> list["CollectionSchema"]:
        return [
            cls.model_validate(c)
            for c in collections
            if c.user_id == user_id or c.is_public
        ]
