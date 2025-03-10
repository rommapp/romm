from datetime import datetime

from models.collection import Collection

from .base import BaseModel


class BaseCollectionSchema(BaseModel):
    name: str
    description: str
    rom_ids: set[int]
    rom_count: int
    path_cover_small: str | None
    path_cover_large: str | None
    path_covers_small: list[str]
    path_covers_large: list[str]


class CollectionSchema(BaseCollectionSchema):
    id: int
    url_cover: str | None
    rom_ids: set[int]
    rom_count: int
    user_id: int
    user__username: str
    is_public: bool
    is_favorite: bool
    is_virtual: bool = False

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


class VirtualCollectionSchema(BaseCollectionSchema):
    id: str
    type: str
    is_public: bool = True
    is_favorite: bool = False
    is_virtual: bool = True

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
