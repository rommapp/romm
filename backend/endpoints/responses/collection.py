from collections.abc import Sequence
from typing import Any

from pydantic import ConfigDict, computed_field

from models.collection import Collection, SmartCollection

from .base import BaseModel, UTCDatetime


class BaseCollectionSchema(BaseModel):
    """A set of roms: a regular, virtual or smart collection."""

    name: str
    description: str
    rom_ids: set[int]
    """The IDs of the roms in the collection. Roms hidden from the caller are left out."""
    path_cover_small: str | None
    path_cover_large: str | None
    path_covers_small: list[str]
    """The small covers of the roms in the collection, used to build a collage when `path_cover_small` is empty."""
    path_covers_large: list[str]
    """The large covers of the roms in the collection, used to build a collage when `path_cover_large` is empty."""
    is_public: bool = False
    is_favorite: bool = False
    is_virtual: bool = False
    """True for a virtual collection, which is generated from the library's metadata."""
    is_smart: bool = False
    """True for a smart collection, whose roms are chosen by its filters."""
    created_at: UTCDatetime
    updated_at: UTCDatetime

    # Derived from `rom_ids` so it stays right after hidden roms are dropped.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def rom_count(self) -> int:
        """The number of roms in the collection."""
        return len(self.rom_ids)


class CollectionSchema(BaseCollectionSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url_cover: str | None
    """The remote URL the cover was fetched from."""
    user_id: int
    owner_username: str

    @classmethod
    def for_user(
        cls, user_id: int, collections: Sequence["Collection"]
    ) -> list["CollectionSchema"]:
        return [
            cls.model_validate(c)
            for c in collections
            if c.user_id == user_id or c.is_public
        ]


class VirtualCollectionSchema(BaseCollectionSchema):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    """The kind of virtual collection: `genre`, `franchise`, `collection`, `mode`, `company`, `publisher` or `developer`."""
    is_virtual: bool = True
    """Always true."""


class SmartCollectionSchema(BaseCollectionSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str = ""
    filter_criteria: dict[str, Any]
    filter_summary: str
    user_id: int
    owner_username: str
    is_smart: bool = True
    """Always true."""

    @classmethod
    def for_user(
        cls, user_id: int, smart_collections: Sequence["SmartCollection"]
    ) -> list["SmartCollectionSchema"]:
        """Filter smart collections visible to user and create schemas."""
        return [
            cls.model_validate(c)
            for c in smart_collections
            if c.user_id == user_id or c.is_public
        ]
