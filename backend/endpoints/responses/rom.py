from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, NotRequired, TypedDict, get_type_hints

from fastapi import Request
from pydantic import Field, computed_field, field_validator

from endpoints.responses.assets import SaveSchema, ScreenshotSchema, StateSchema
from handler.metadata.flashpoint_handler import FlashpointMetadata
from handler.metadata.gamelist_handler import GamelistMetadata
from handler.metadata.hasheous_handler import HasheousMetadata
from handler.metadata.hltb_handler import HLTBMetadata
from handler.metadata.igdb_handler import IGDBMetadata
from handler.metadata.launchbox_handler import LaunchboxMetadata
from handler.metadata.moby_handler import MobyMetadata
from handler.metadata.ra_handler import RAMetadata
from handler.metadata.ss_handler import SSMetadata
from models.collection import Collection
from models.rom import Rom, RomFileCategory, RomUserStatus

from .base import BaseModel

SORT_COMPARE_REGEX = re.compile(r"^([Tt]he|[Aa]|[Aa]nd)\s")


class UserNoteSchema(BaseModel):
    id: int
    title: str
    content: str
    is_public: bool
    tags: list[str] | None = None
    created_at: datetime
    updated_at: datetime
    user_id: int
    username: str

    class Config:
        from_attributes = True


RomIGDBMetadata = TypedDict(  # type: ignore[misc]
    "RomIGDBMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(IGDBMetadata).items()},  # type: ignore[misc]
    total=False,
)
RomMobyMetadata = TypedDict(  # type: ignore[misc]
    "RomMobyMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(MobyMetadata).items()},  # type: ignore[misc]
    total=False,
)
RomSSMetadata = TypedDict(  # type: ignore[misc]
    "RomSSMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(SSMetadata).items()},  # type: ignore[misc]
    total=False,
)
RomRAMetadata = TypedDict(  # type: ignore[misc]
    "RomRAMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(RAMetadata).items()},  # type: ignore[misc]
    total=False,
)
RomLaunchboxMetadata = TypedDict(  # type: ignore[misc]
    "RomLaunchboxMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(LaunchboxMetadata).items()},  # type: ignore[misc]
    total=False,
)
RomHasheousMetadata = TypedDict(  # type: ignore[misc]
    "RomHasheousMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(HasheousMetadata).items()},  # type: ignore[misc]
    total=False,
)
RomFlashpointMetadata = TypedDict(  # type: ignore[misc]
    "RomFlashpointMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(FlashpointMetadata).items()},  # type: ignore[misc]
    total=False,
)
RomHLTBMetadata = TypedDict(  # type: ignore[misc]
    "RomHLTBMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(HLTBMetadata).items()},  # type: ignore[misc]
    total=False,
)
RomGamelistMetadata = TypedDict(  # type: ignore[misc]
    "RomGamelistMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(GamelistMetadata).items()},  # type: ignore[misc]
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
    launchbox_id: int | None
    hasheous_id: int | None
    tgdb_id: int | None
    flashpoint_id: str | None
    hltb_id: int | None
    gamelist_id: str | None

    platform_id: int
    platform_slug: str
    platform_fs_slug: str
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
    launchbox_metadata: RomLaunchboxMetadata | None
    hasheous_metadata: RomHasheousMetadata | None
    flashpoint_metadata: RomFlashpointMetadata | None
    hltb_metadata: RomHLTBMetadata | None
    gamelist_metadata: RomGamelistMetadata | None

    path_cover_small: str | None
    path_cover_large: str | None
    url_cover: str | None

    has_manual: bool
    path_manual: str | None
    url_manual: str | None

    is_identifying: bool = False
    is_unidentified: bool
    is_identified: bool

    revision: str | None
    regions: list[str]
    languages: list[str]
    tags: list[str]

    crc_hash: str | None
    md5_hash: str | None
    sha1_hash: str | None

    # TODO: Remove this after 4.3 release
    multi: Annotated[bool, Field(deprecated="Replaced by has_multiple_files")]
    has_simple_single_file: bool
    has_nested_single_file: bool
    has_multiple_files: bool
    files: list[RomFileSchema]
    full_path: str
    created_at: datetime
    updated_at: datetime
    missing_from_fs: bool

    siblings: list[SiblingRomSchema]
    rom_user: RomUserSchema

    class Config:
        from_attributes = True

    @classmethod
    def populate_properties(cls, db_rom: Rom, request: Request) -> Rom:
        db_rom.rom_user = RomUserSchema.for_user(request.user.id, db_rom)  # type: ignore
        db_rom.siblings = [  # type: ignore
            SiblingRomSchema(
                id=s.id,
                name=s.name,
                fs_name_no_tags=s.fs_name_no_tags,
                fs_name_no_ext=s.fs_name_no_ext,
            )
            for s in db_rom.sibling_roms
        ]
        return db_rom

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, _request: Request) -> RomSchema:
        return cls.model_validate(db_rom)

    @field_validator("alternative_names")
    def sort_alternative_names(cls, v: list[str]) -> list[str]:
        return sorted(v)

    @field_validator("files")
    def sort_files(cls, v: list[RomFileSchema]) -> list[RomFileSchema]:
        return sorted(v, key=lambda x: x.file_name)

    @field_validator("siblings")
    def sort_siblings(cls, v: list[SiblingRomSchema]) -> list[SiblingRomSchema]:
        return sorted(v, key=lambda x: x.sort_comparator)


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
    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> SimpleRomSchema:
        db_rom = cls.populate_properties(db_rom, request)
        return cls.model_validate(db_rom)

    @classmethod
    def from_orm_with_factory(cls, db_rom: Rom) -> SimpleRomSchema:
        db_rom.rom_user = rom_user_schema_factory()  # type: ignore
        db_rom.siblings = []  # type: ignore
        return cls.model_validate(db_rom)


class UserCollectionSchema(BaseModel):
    id: int
    name: str

    @classmethod
    def for_user(
        cls, user_id: int, collections: list[Collection]
    ) -> list["UserCollectionSchema"]:
        return [
            UserCollectionSchema(
                id=c.id,
                name=c.name,
            )
            for c in collections
            if c.user_id == user_id or c.is_public
        ]


class DetailedRomSchema(RomSchema):
    merged_ra_metadata: RomRAMetadata | None
    merged_screenshots: list[str]
    user_saves: list[SaveSchema]
    user_states: list[StateSchema]
    user_screenshots: list[ScreenshotSchema]
    user_collections: list[UserCollectionSchema]
    all_user_notes: list[UserNoteSchema]

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> DetailedRomSchema:
        user_id = request.user.id
        db_rom = cls.populate_properties(db_rom, request)

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
        db_rom.user_collections = UserCollectionSchema.for_user(  # type: ignore
            user_id, db_rom.collections
        )

        # Load notes separately using the database handler to avoid lazy loading issues
        from handler.database import db_rom_handler

        notes = db_rom_handler.get_rom_notes(rom_id=db_rom.id, user_id=user_id)

        # Convert notes to schema format
        all_notes = []
        for note in notes:
            note_dict = {
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "is_public": note.is_public,
                "tags": note.tags,
                "created_at": note.created_at,
                "updated_at": note.updated_at,
                "user_id": note.user_id,
                "username": note.user.username,
            }
            all_notes.append(UserNoteSchema.model_validate(note_dict))

        # Sort notes by updated_at (most recent first)
        all_notes.sort(key=lambda x: x.updated_at, reverse=True)
        db_rom.all_user_notes = all_notes  # type: ignore

        return cls.model_validate(db_rom)

    @field_validator("user_saves")
    def sort_user_saves(cls, v: list[SaveSchema]) -> list[SaveSchema]:
        return sorted(v, key=lambda x: x.updated_at, reverse=True)

    @field_validator("user_states")
    def sort_user_states(cls, v: list[StateSchema]) -> list[StateSchema]:
        return sorted(v, key=lambda x: x.updated_at, reverse=True)

    @field_validator("user_screenshots")
    def sort_user_screenshots(cls, v: list[ScreenshotSchema]) -> list[ScreenshotSchema]:
        return sorted(v, key=lambda x: x.created_at, reverse=True)
