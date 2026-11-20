from collections.abc import Sequence
from typing import Any

from pydantic import ConfigDict, computed_field

from models.collection import Collection, SmartCollection

from .base import BaseModel, UTCDatetime


class BaseCollectionSchema(BaseModel):
    """A set of roms: a regular, virtual or smart collection."""

    name: str
    """The name of the collection."""
    description: str
    """The description of the collection."""
    rom_ids: set[int]
    """The IDs of the roms in the collection. Roms hidden from the caller are left out."""
    path_cover_small: str | None
    """The path to the small cover image."""
    path_cover_large: str | None
    """The path to the large cover image."""
    path_covers_small: list[str]
    """The paths to the small covers shown for the collection."""
    path_covers_large: list[str]
    """The paths to the large covers shown for the collection."""
    is_public: bool = False
    """Whether other users can see the collection."""
    is_favorite: bool = False
    """Whether the collection is marked as a favorite."""
    is_virtual: bool = False
    """True for a virtual collection, which the library's metadata generates."""
    is_smart: bool = False
    """True for a smart collection, which its filters define."""
    created_at: UTCDatetime
    """When the collection was created."""
    updated_at: UTCDatetime
    """When the collection last changed."""

    # Derived from `rom_ids` so it stays right after hidden roms are dropped.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def rom_count(self) -> int:
        """The number of roms in the collection."""
        return len(self.rom_ids)


class CollectionSchema(BaseCollectionSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    """The internal ID of the collection."""
    url_cover: str | None
    """The remote URL the cover was fetched from."""
    user_id: int
    """The ID of the user who owns the collection."""
    owner_username: str
    """The username of the owner."""

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
    """The ID of the virtual collection."""
    type: str
    """The kind of virtual collection: `genre`, `franchise`, `collection`, `mode`, `company`, `publisher` or `developer`."""
    is_virtual: bool = True
    """Always true."""


class SmartCollectionSchema(BaseCollectionSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    """The internal ID of the smart collection."""
    name: str
    """The name of the smart collection."""
    description: str = ""
    """The description of the smart collection."""
    filter_criteria: dict[str, Any]
    """The filters that define the collection."""
    filter_summary: str
    """A short text summary of the filters."""
    user_id: int
    """The ID of the user who owns the collection."""
    owner_username: str
    """The username of the owner."""
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
