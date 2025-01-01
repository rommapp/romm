from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import NotRequired, TypedDict, get_type_hints

from endpoints.responses.assets import SaveSchema, ScreenshotSchema, StateSchema
from endpoints.responses.collection import CollectionSchema
from fastapi import Request
from handler.metadata.igdb_handler import IGDBMetadata
from handler.metadata.moby_handler import MobyMetadata
from models.rom import Rom, RomFile, RomUserStatus
from pydantic import BaseModel, computed_field

SORT_COMPARE_REGEX = re.compile(r"^([Tt]he|[Aa]|[Aa]nd)\s")

RomIGDBMetadata = TypedDict(  # type: ignore[misc]
    "RomIGDBMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(IGDBMetadata).items()},
    total=False,
)
RomMobyMetadata = TypedDict(  # type: ignore[misc]
    "RomMobyMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(MobyMetadata).items()},
    total=False,
)


def rom_user_schema_factory() -> RomUserSchema:
    now = datetime.now(timezone.utc)
    return RomUserSchema(
        id=-1,
        user_id=-1,
        rom_id=-1,
        created_at=now,
        updated_at=now,
        last_played=None,
        note_raw_markdown="",
        note_is_public=False,
        is_main_sibling=False,
        backlogged=False,
        now_playing=False,
        hidden=False,
        rating=0,
        difficulty=0,
        completion=0,
        status=None,
        user__username="",
    )


class RomUserSchema(BaseModel):
    id: int
    user_id: int
    rom_id: int
    created_at: datetime
    updated_at: datetime
    last_played: datetime | None
    note_raw_markdown: str
    note_is_public: bool
    is_main_sibling: bool
    backlogged: bool
    now_playing: bool
    hidden: bool
    rating: int
    difficulty: int
    completion: int
    status: RomUserStatus | None
    user__username: str

    class Config:
        from_attributes = True

    @classmethod
    def for_user(cls, user_id: int, db_rom: Rom) -> RomUserSchema:
        for n in db_rom.rom_users:
            if n.user_id == user_id:
                return cls.model_validate(n)

        # Return a dummy RomUserSchema if the user + rom combination doesn't exist
        return rom_user_schema_factory()

    @classmethod
    def notes_for_user(cls, user_id: int, db_rom: Rom) -> list[UserNotesSchema]:
        return [
            {
                "user_id": n.user_id,
                "username": n.user__username,
                "note_raw_markdown": n.note_raw_markdown,
            }
            for n in db_rom.rom_users
            # This is what filters out private notes
            if n.user_id == user_id or n.note_is_public
        ]


class RomSchema(BaseModel):
    id: int
    igdb_id: int | None
    sgdb_id: int | None
    moby_id: int | None

    platform_id: int
    platform_slug: str
    platform_fs_slug: str
    platform_name: str
    platform_custom_name: str | None
    platform_display_name: str

    file_name: str
    file_name_no_tags: str
    file_name_no_ext: str
    file_extension: str
    file_path: str
    file_size_bytes: int

    name: str | None
    slug: str | None
    summary: str | None

    # Metadata fields
    first_release_date: int | None
    youtube_video_id: str | None
    alternative_names: list[str]
    genres: list[str]
    franchises: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
    age_ratings: list[str]
    igdb_metadata: RomIGDBMetadata | None
    moby_metadata: RomMobyMetadata | None

    path_cover_s: str | None
    path_cover_l: str | None
    has_cover: bool
    url_cover: str | None

    revision: str | None
    regions: list[str]
    languages: list[str]
    tags: list[str]

    multi: bool
    files: list[RomFile]
    crc_hash: str | None
    md5_hash: str | None
    sha1_hash: str | None
    full_path: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @computed_field  # type: ignore
    @property
    def sort_comparator(self) -> str:
        return (
            SORT_COMPARE_REGEX.sub(
                "",
                self.name or self.file_name_no_tags,
            )
            .strip()
            .lower()
        )


class SimpleRomSchema(RomSchema):
    sibling_roms: list[RomSchema]
    rom_user: RomUserSchema

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> SimpleRomSchema:
        user_id = request.user.id

        db_rom.rom_user = RomUserSchema.for_user(user_id, db_rom)

        return cls.model_validate(db_rom)

    @classmethod
    def from_orm_with_factory(cls, db_rom: Rom) -> SimpleRomSchema:
        db_rom.rom_user = rom_user_schema_factory()

        return cls.model_validate(db_rom)


class DetailedRomSchema(RomSchema):
    merged_screenshots: list[str]
    sibling_roms: list[RomSchema]
    rom_user: RomUserSchema
    user_saves: list[SaveSchema]
    user_states: list[StateSchema]
    user_screenshots: list[ScreenshotSchema]
    user_notes: list[UserNotesSchema]
    user_collections: list[CollectionSchema]

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> DetailedRomSchema:
        user_id = request.user.id

        db_rom.rom_user = RomUserSchema.for_user(user_id, db_rom)
        db_rom.user_notes = RomUserSchema.notes_for_user(user_id, db_rom)
        db_rom.user_saves = [
            SaveSchema.model_validate(s) for s in db_rom.saves if s.user_id == user_id
        ]
        db_rom.user_states = [
            StateSchema.model_validate(s) for s in db_rom.states if s.user_id == user_id
        ]
        db_rom.user_screenshots = [
            ScreenshotSchema.model_validate(s)
            for s in db_rom.screenshots
            if s.user_id == user_id
        ]
        db_rom.user_collections = CollectionSchema.for_user(
            user_id, db_rom.get_collections()
        )

        return cls.model_validate(db_rom)


class UserNotesSchema(TypedDict):
    user_id: int
    username: str
    note_raw_markdown: str
