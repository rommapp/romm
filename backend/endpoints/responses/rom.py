from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import NotRequired, TypedDict, get_type_hints

from endpoints.responses.assets import SaveSchema, ScreenshotSchema, StateSchema
from endpoints.responses.collection import CollectionSchema
from fastapi import Request
from handler.metadata.igdb_handler import IGDBMetadata
from handler.metadata.moby_handler import MobyMetadata
from handler.metadata.ra_handler import RAMetadata
from handler.metadata.ss_handler import SSMetadata
from models.rom import Rom, RomFileCategory, RomUserStatus
from pydantic import computed_field, field_validator

from .base import BaseModel

SORT_COMPARE_REGEX = re.compile(r"^([Tt]he|[Aa]|[Aa]nd)\s")

RomIGDBMetadata = TypedDict(  # type: ignore[misc]
    "RomIGDBMetadata",
    dict((k, NotRequired[v]) for k, v in get_type_hints(IGDBMetadata).items()),
    total=False,
)
RomMobyMetadata = TypedDict(  # type: ignore[misc]
    "RomMobyMetadata",
    dict((k, NotRequired[v]) for k, v in get_type_hints(MobyMetadata).items()),
    total=False,
)
RomSSMetadata = TypedDict(  # type: ignore[misc]
    "RomSSMetadata",
    dict((k, NotRequired[v]) for k, v in get_type_hints(SSMetadata).items()),
    total=False,
)
RomRAMetadata = TypedDict(  # type: ignore[misc]
    "RomRAMetadata",
    dict((k, NotRequired[v]) for k, v in get_type_hints(RAMetadata).items()),
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


class RomFileSchema(BaseModel):
    id: int
    rom_id: int
    file_name: str
    file_path: str
    file_size_bytes: int
    full_path: str
    created_at: datetime
    updated_at: datetime
    last_modified: datetime
    crc_hash: str | None
    md5_hash: str | None
    sha1_hash: str | None
    category: RomFileCategory | None

    class Config:
        from_attributes = True


class RomMetadataSchema(BaseModel):
    rom_id: int
    genres: list[str]
    franchises: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
    age_ratings: list[str]
    first_release_date: int | None
    average_rating: float | None

    class Config:
        from_attributes = True

    @field_validator("genres")
    def sort_genres(cls, v: list[str]) -> list[str]:
        return sorted(v)

    @field_validator("franchises")
    def sort_franchises(cls, v: list[str]) -> list[str]:
        return sorted(v)

    @field_validator("collections")
    def sort_collections(cls, v: list[str]) -> list[str]:
        return sorted(v)

    @field_validator("companies")
    def sort_companies(cls, v: list[str]) -> list[str]:
        return sorted(v)

    @field_validator("game_modes")
    def sort_game_modes(cls, v: list[str]) -> list[str]:
        return sorted(v)

    @field_validator("age_ratings")
    def sort_age_ratings(cls, v: list[str]) -> list[str]:
        return sorted(v)


class RomSchema(BaseModel):
    id: int
    igdb_id: int | None
    sgdb_id: int | None
    moby_id: int | None
    ss_id: int | None
    ra_id: int | None

    platform_id: int
    platform_slug: str
    platform_fs_slug: str
    platform_name: str
    platform_custom_name: str | None
    platform_display_name: str

    fs_name: str
    fs_name_no_tags: str
    fs_name_no_ext: str
    fs_extension: str
    fs_path: str
    fs_size_bytes: int

    name: str | None
    slug: str | None
    summary: str | None

    # Metadata fields
    alternative_names: list[str]
    youtube_video_id: str | None
    metadatum: RomMetadataSchema
    igdb_metadata: RomIGDBMetadata | None
    moby_metadata: RomMobyMetadata | None
    ss_metadata: RomSSMetadata | None

    path_cover_small: str | None
    path_cover_large: str | None
    url_cover: str | None

    has_manual: bool
    path_manual: str | None
    url_manual: str | None

    is_unidentified: bool

    revision: str | None
    regions: list[str]
    languages: list[str]
    tags: list[str]

    crc_hash: str | None
    md5_hash: str | None
    sha1_hash: str | None

    multi: bool
    files: list[RomFileSchema]
    full_path: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, _request: Request) -> RomSchema:
        return cls.model_validate(db_rom)

    @field_validator("alternative_names")
    def sort_alternative_names(cls, v: list[str]) -> list[str]:
        return sorted(v)

    @field_validator("files")
    def sort_files(cls, v: list[RomFileSchema]) -> list[RomFileSchema]:
        return sorted(v, key=lambda x: x.file_name)


class SiblingRomSchema(BaseModel):
    id: int
    name: str | None
    fs_name_no_tags: str
    fs_name_no_ext: str

    @computed_field  # type: ignore
    @property
    def sort_comparator(self) -> str:
        return (
            SORT_COMPARE_REGEX.sub(
                "",
                self.name or self.fs_name_no_tags,
            )
            .strip()
            .lower()
        )


class SimpleRomSchema(RomSchema):
    siblings: list[SiblingRomSchema]
    rom_user: RomUserSchema

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> SimpleRomSchema:
        user_id = request.user.id
        db_rom.rom_user = RomUserSchema.for_user(user_id, db_rom)  # type: ignore
        db_rom.siblings = [  # type: ignore
            SiblingRomSchema(
                id=s.id,
                name=s.name,
                fs_name_no_tags=s.fs_name_no_tags,
                fs_name_no_ext=s.fs_name_no_ext,
            )
            for s in db_rom.sibling_roms
        ]
        return cls.model_validate(db_rom)

    @classmethod
    def from_orm_with_factory(cls, db_rom: Rom) -> SimpleRomSchema:
        db_rom.rom_user = rom_user_schema_factory()  # type: ignore
        db_rom.siblings = []  # type: ignore
        return cls.model_validate(db_rom)

    @field_validator("siblings")
    def sort_siblings(cls, v: list[SiblingRomSchema]) -> list[SiblingRomSchema]:
        return sorted(v, key=lambda x: x.sort_comparator)


class DetailedRomSchema(RomSchema):
    merged_ra_metadata: RomRAMetadata | None
    merged_screenshots: list[str]
    siblings: list[SiblingRomSchema]
    rom_user: RomUserSchema
    user_saves: list[SaveSchema]
    user_states: list[StateSchema]
    user_screenshots: list[ScreenshotSchema]
    user_notes: list[UserNotesSchema]
    user_collections: list[CollectionSchema]

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> DetailedRomSchema:
        user_id = request.user.id

        db_rom.rom_user = RomUserSchema.for_user(user_id, db_rom)  # type: ignore
        db_rom.user_notes = RomUserSchema.notes_for_user(user_id, db_rom)  # type: ignore
        db_rom.user_saves = [  # type: ignore
            SaveSchema.model_validate(s) for s in db_rom.saves if s.user_id == user_id
        ]
        db_rom.user_states = [  # type: ignore
            StateSchema.model_validate(s) for s in db_rom.states if s.user_id == user_id
        ]
        db_rom.user_screenshots = [  # type: ignore
            ScreenshotSchema.model_validate(s)
            for s in db_rom.screenshots
            if s.user_id == user_id
        ]
        db_rom.user_collections = CollectionSchema.for_user(  # type: ignore
            user_id, db_rom.collections
        )
        db_rom.siblings = [  # type: ignore
            SiblingRomSchema(
                id=s.id,
                name=s.name,
                fs_name_no_tags=s.fs_name_no_tags,
                fs_name_no_ext=s.fs_name_no_ext,
            )
            for s in db_rom.sibling_roms
        ]

        return cls.model_validate(db_rom)

    @field_validator("siblings")
    def sort_siblings(cls, v: list[SiblingRomSchema]) -> list[SiblingRomSchema]:
        return sorted(v, key=lambda x: x.sort_comparator)

    @field_validator("user_saves")
    def sort_user_saves(cls, v: list[SaveSchema]) -> list[SaveSchema]:
        return sorted(v, key=lambda x: x.updated_at, reverse=True)

    @field_validator("user_states")
    def sort_user_states(cls, v: list[StateSchema]) -> list[StateSchema]:
        return sorted(v, key=lambda x: x.updated_at, reverse=True)

    @field_validator("user_screenshots")
    def sort_user_screenshots(cls, v: list[ScreenshotSchema]) -> list[ScreenshotSchema]:
        return sorted(v, key=lambda x: x.created_at, reverse=True)


class UserNotesSchema(TypedDict):
    user_id: int
    username: str
    note_raw_markdown: str
