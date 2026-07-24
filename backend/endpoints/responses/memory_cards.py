from pydantic import ConfigDict

from .base import BaseModel, UTCDatetime


class MemoryCardVersionSchema(BaseModel):
    """A single snapshot in a card's history. Unlike the ROM-scoped assets it
    has no rom_id/user_id, so it does not reuse the shared BaseAsset schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    memory_card_id: int
    file_name: str
    file_size_bytes: int
    content_hash: str | None = None
    download_path: str
    missing_from_fs: bool

    created_at: UTCDatetime
    updated_at: UTCDatetime


class MemoryCardSchema(BaseModel):
    """A card's identity. Its data lives in `versions`; the list views return
    the card without them (fetch history via the versions route) so the schema
    never touches the lazy="raise" relationship."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    emulator: str
    platform_id: int | None = None
    name: str
    slot: int
    is_public: bool = False

    created_at: UTCDatetime
    updated_at: UTCDatetime


class UserMemoryCardSchema(MemoryCardSchema):
    """A card enriched with its owner's username, for the shared/community
    picker. Mirrors UserStateSchema."""

    username: str
    user_avatar_path: str = ""
    user_updated_at: UTCDatetime | None = None
