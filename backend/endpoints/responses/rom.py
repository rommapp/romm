from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import NotRequired, TypedDict, get_type_hints

from fastapi import Request
from pydantic import ConfigDict, Field, computed_field, field_validator

from endpoints.responses.assets import (
    SaveSchema,
    ScreenshotSchema,
    StateSchema,
    UserScreenshotSchema,
)
from handler.metadata.flashpoint_handler import FlashpointMetadata
from handler.metadata.gamelist_handler import GamelistMetadata
from handler.metadata.hasheous_handler import HasheousMetadata
from handler.metadata.hltb_handler import HLTBMetadata
from handler.metadata.igdb_handler import IGDBMetadata
from handler.metadata.launchbox_handler.types import LaunchboxMetadata
from handler.metadata.moby_handler import MobyMetadata
from handler.metadata.ra_handler import RAMetadata
from handler.metadata.ss_handler import SSMetadata
from models.collection import Collection
from models.rom import Rom, RomArchiveMember, RomFile, RomFileCategory, RomUserStatus

from .base import BaseModel, UTCDatetime

SORT_COMPARE_REGEX = re.compile(r"^([Tt]he|[Aa]|[Aa]nd)\s")


class UserNoteSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    is_public: bool
    tags: list[str] | None = None
    created_at: UTCDatetime
    updated_at: UTCDatetime
    user_id: int
    username: str


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
ManualMetadata = TypedDict(
    "ManualMetadata",
    {
        "genres": list[str] | None,
        "franchises": list[str] | None,
        "companies": list[str] | None,
        "game_modes": list[str] | None,
        "age_ratings": list[str] | None,
        "first_release_date": int | None,
        "youtube_video_id": str | None,
    },
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
    )


class RomUserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    rom_id: int
    created_at: UTCDatetime
    updated_at: UTCDatetime
    last_played: UTCDatetime | None
    is_main_sibling: bool
    backlogged: bool
    now_playing: bool
    hidden: bool
    rating: int
    difficulty: int
    completion: int
    status: RomUserStatus | None

    @classmethod
    def for_user(cls, user_id: int, db_rom: Rom) -> RomUserSchema:
        for n in db_rom.rom_users:
            if n.user_id == user_id:
                return cls.model_validate(n)

        # Return a dummy RomUserSchema if the user + rom combination doesn't exist
        return rom_user_schema_factory()


class RomFileAudioMetaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str | None = None
    artist: str | None = None
    album: str | None = None
    year: str | None = None
    genre: str | None = None
    track: str | None = None
    disc: str | None = None
    duration_seconds: float | None = None
    has_embedded_cover: bool = False
    cover_path: str | None = None


class RomFileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rom_id: int
    file_name: str
    file_path: str
    file_size_bytes: int
    full_path: str
    created_at: UTCDatetime
    updated_at: UTCDatetime
    last_modified: UTCDatetime
    crc_hash: str | None
    md5_hash: str | None
    sha1_hash: str | None
    ra_hash: str | None
    chd_sha1_hash: str | None
    archive_members: list[RomArchiveMember] | None
    category: RomFileCategory | None
    audio_meta: RomFileAudioMetaSchema | None = None


class SoundtrackTrackMetaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: int
    file_name: str
    file_size_bytes: int
    audio_meta: RomFileAudioMetaSchema | None = None


class RomMetadataSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rom_id: int
    genres: list[str]
    franchises: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
    age_ratings: list[str]
    player_count: str
    first_release_date: int | None
    average_rating: float | None

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

    @field_validator("age_ratings", mode="before")
    def normalize_age_ratings(cls, v: str | list[str] | None) -> list[str]:
        if not v:
            return []

        # MySQL/MariaDB returns a scalar string instead of a single-element array
        # when using JSON_EXTRACT with a [*] wildcard path on a single-element array.
        if isinstance(v, str):
            return sorted([v])

        return sorted(v)


class RomSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    libretro_id: str | None

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
    manual_metadata: ManualMetadata | None

    path_cover_small: str | None
    path_cover_large: str | None
    url_cover: str | None

    has_manual: bool
    has_manual_files: bool
    has_soundtrack: bool
    path_manual: str | None
    url_manual: str | None

    path_video: str | None

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
    ra_hash: str | None

    has_simple_single_file: bool
    has_nested_single_file: bool
    has_multiple_files: bool
    full_path: str
    created_at: UTCDatetime
    updated_at: UTCDatetime
    missing_from_fs: bool
    has_notes: bool

    rom_user: RomUserSchema
    merged_screenshots: list[str]
    merged_ra_metadata: RomRAMetadata | None

    files: list[RomFileSchema] = Field(validation_alias="included_files")
    sibling_roms: list[SiblingRomSchema] = Field(
        validation_alias="included_sibling_roms"
    )

    @field_validator("files")
    def sort_files(cls, v: list[RomFileSchema]) -> list[RomFileSchema]:
        return sorted(v, key=lambda x: x.file_name)

    @field_validator("sibling_roms")
    def sort_sibling_roms(cls, v: list[SiblingRomSchema]) -> list[SiblingRomSchema]:
        return sorted(v, key=lambda x: x.sort_comparator)

    @classmethod
    def populate_properties(cls, db_rom: Rom, request: Request) -> Rom:
        db_rom.rom_user = RomUserSchema.for_user(request.user.id, db_rom)  # type: ignore[assignment]
        db_rom.has_notes = any(  # type: ignore[assignment]
            note.is_public or note.user_id == request.user.id for note in db_rom.notes
        )
        return db_rom

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, _request: Request) -> RomSchema:
        return cls.model_validate(db_rom)

    @field_validator("alternative_names")
    def sort_alternative_names(cls, v: list[str]) -> list[str]:
        return sorted(v)


class SiblingRomSchema(BaseModel):
    id: int
    name: str | None
    fs_name_no_tags: str
    fs_name_no_ext: str
    is_main_sibling: bool

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

    @classmethod
    def from_rom(cls, rom: Rom, *, is_main_sibling: bool = False) -> SiblingRomSchema:
        return cls(
            id=rom.id,
            name=rom.name,
            fs_name_no_tags=rom.fs_name_no_tags,
            fs_name_no_ext=rom.fs_name_no_ext,
            is_main_sibling=is_main_sibling,
        )


class SimpleRomSchema(RomSchema):
    @classmethod
    def from_orm_with_request(
        cls,
        db_rom: Rom,
        request: Request,
        files: Sequence[RomFile] | None = None,
        siblings: Sequence[tuple[Rom, bool]] | None = None,
    ) -> SimpleRomSchema:
        db_rom = cls.populate_properties(db_rom, request)

        # The list endpoint passes pre-fetched `files`/`siblings` (batched via
        # get_files_for_roms / get_siblings_for_roms, no per-row hydration).
        # Single-rom endpoints (e.g. `/{id}/simple`, loaded via the
        # `with_details` decorator) pass neither and fall back to the
        # eager-loaded relationships. `None` (not provided) is distinct from an
        # explicit empty list (e.g. the gallery list, which intentionally omits
        # files unless `with_files` is set).
        if files is None:
            files = db_rom.files
        if siblings is None:
            user_id = request.user.id
            siblings = [
                (
                    s,
                    any(
                        ru.user_id == user_id and ru.is_main_sibling
                        for ru in s.rom_users
                    ),
                )
                for s in db_rom.sibling_roms
            ]

        db_rom.included_files = list(files)  # type: ignore[assignment]
        db_rom.included_sibling_roms = [  # type: ignore[assignment]
            SiblingRomSchema.from_rom(s, is_main_sibling=is_main)
            for s, is_main in siblings
        ]
        return cls.model_validate(db_rom)

    @classmethod
    def from_orm_with_factory(cls, db_rom: Rom) -> SimpleRomSchema:
        db_rom.rom_user = rom_user_schema_factory()  # type: ignore[assignment]
        db_rom.included_files = []  # type: ignore[assignment]
        db_rom.included_sibling_roms = []  # type: ignore[assignment]
        db_rom.has_notes = False  # type: ignore[assignment]
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
    user_saves: list[SaveSchema]
    user_states: list[StateSchema]
    user_screenshots: list[ScreenshotSchema]
    all_user_screenshots: list[UserScreenshotSchema]
    user_collections: list[UserCollectionSchema]
    all_user_notes: list[UserNoteSchema]

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> DetailedRomSchema:
        user_id = request.user.id
        db_rom = cls.populate_properties(db_rom, request)

        sorted_siblings = sorted(
            (
                SiblingRomSchema.from_rom(
                    s,
                    is_main_sibling=any(
                        ru.user_id == user_id and ru.is_main_sibling
                        for ru in s.rom_users
                    ),
                )
                for s in db_rom.sibling_roms
            ),
            key=lambda x: x.sort_comparator,
        )
        db_rom.included_sibling_roms = sorted_siblings  # type: ignore[assignment]
        db_rom.included_files = sorted(db_rom.files, key=lambda x: x.file_name)  # type: ignore[assignment]

        db_rom.user_saves = [  # type: ignore[assignment]
            SaveSchema.model_validate(s) for s in db_rom.saves if s.user_id == user_id
        ]
        db_rom.user_states = [  # type: ignore[assignment]
            StateSchema.model_validate(s) for s in db_rom.states if s.user_id == user_id
        ]
        db_rom.user_screenshots = [  # type: ignore[assignment]
            ScreenshotSchema.model_validate(s)
            for s in db_rom.screenshots
            if s.user_id == user_id
        ]
        db_rom.user_collections = UserCollectionSchema.for_user(  # type: ignore[assignment]
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
        db_rom.all_user_notes = all_notes  # type: ignore[assignment]

        # Gallery screenshots visible to this user: own (public + private) plus
        # other users' public ones. Mirrors the notes flow above. Excludes the
        # auto-captured save/state thumbnails (is_gallery == False).
        from handler.database import db_screenshot_handler

        gallery_screenshots = db_screenshot_handler.get_rom_gallery_screenshots(
            rom_id=db_rom.id, user_id=user_id
        )
        db_rom.all_user_screenshots = [  # type: ignore[assignment]
            UserScreenshotSchema.model_validate(
                {
                    **{
                        field: getattr(s, field)
                        for field in ScreenshotSchema.model_fields
                    },
                    "username": s.user.username,
                }
            )
            for s in gallery_screenshots
        ]

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


class RomFiltersDict(TypedDict):
    genres: list[str]
    franchises: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
    age_ratings: list[str]
    player_counts: list[str]
    regions: list[str]
    languages: list[str]
    platforms: list[int]
