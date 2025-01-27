from datetime import datetime

from models.collection import Collection

from .base import BaseModel


class CollectionSchema(BaseModel):
    id: int
    name: str
    description: str
    path_cover_small: str | None
    path_cover_large: str | None
    url_cover: str
    roms: set[int]
    rom_count: int
    user_id: int
    user__username: str
    is_public: bool
    is_favorite: bool

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


class VirtualCollectionSchema(BaseModel):
    id: str
    name: str
    type: str
    description: str
    roms: set[int]
    rom_count: int

    class Config:
        from_attributes = True
