from datetime import datetime
from typing import Any

from models.collection import Collection, SmartCollection

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
    is_public: bool = False
    is_favorite: bool = False
    is_virtual: bool = False
    is_smart: bool = False
    created_at: datetime
    updated_at: datetime


class CollectionSchema(BaseCollectionSchema):
    id: int
    url_cover: str | None
    user_id: int
    user__username: str

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
    is_virtual: bool = True

    class Config:
        from_attributes = True


class SmartCollectionSchema(BaseCollectionSchema):
    id: int
    name: str
    description: str = ""
    filter_criteria: dict[str, Any]
    filter_summary: str
    user_id: int
    user__username: str
    is_smart: bool = True

    class Config:
        from_attributes = True

    @classmethod
    def for_user(
        cls, user_id: int, smart_collections: list["SmartCollection"]
    ) -> list["SmartCollectionSchema"]:
        """Filter smart collections visible to user and create schemas."""
        return [
            cls.model_validate(c)
            for c in smart_collections
            if c.user_id == user_id or c.is_public
        ]
