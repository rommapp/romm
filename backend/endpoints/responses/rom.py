from __future__ import annotations

import re
from datetime import datetime
from typing import NotRequired, get_type_hints

from endpoints.responses.assets import SaveSchema, ScreenshotSchema, StateSchema
from endpoints.responses.collection import CollectionSchema
from fastapi import Request
from fastapi.responses import StreamingResponse
from handler.metadata.igdb_handler import IGDBMetadata
from handler.metadata.moby_handler import MobyMetadata
from handler.socket_handler import socket_handler
from models.rom import Rom
from pydantic import BaseModel, Field, computed_field
from typing_extensions import TypedDict

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


class RomUserSchema(BaseModel):
    id: int
    user_id: int
    rom_id: int
    created_at: datetime
    updated_at: datetime
    note_raw_markdown: str
    note_is_public: bool
    is_main_sibling: bool
    user__username: str

    class Config:
        from_attributes = True

    @classmethod
    def for_user(cls, db_rom: Rom, user_id: int) -> RomUserSchema | None:
        for n in db_rom.rom_users:
            if n.user_id == user_id:
                return cls.model_validate(n)

        return None

    @classmethod
    def notes_for_user(cls, db_rom: Rom, user_id: int) -> list[UserNotesSchema]:
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
    platform_name: str

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
    alternative_names: list[str]
    genres: list[str]
    franchises: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
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
    files: list[str]
    full_path: str
    created_at: datetime
    updated_at: datetime

    rom_user: RomUserSchema | None = Field(default=None)

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> RomSchema:
        rom = cls.model_validate(db_rom)
        user_id = request.user.id

        rom.rom_user = RomUserSchema.for_user(db_rom, user_id)

        return rom

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


class DetailedRomSchema(RomSchema):
    merged_screenshots: list[str]
    rom_user: RomUserSchema | None = Field(default=None)
    sibling_roms: list[RomSchema] = Field(default_factory=list)
    user_saves: list[SaveSchema] = Field(default_factory=list)
    user_states: list[StateSchema] = Field(default_factory=list)
    user_screenshots: list[ScreenshotSchema] = Field(default_factory=list)
    user_notes: list[UserNotesSchema] = Field(default_factory=list)
    user_collections: list[CollectionSchema] = Field(default_factory=list)

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> DetailedRomSchema:
        rom = cls.model_validate(db_rom)
        user_id = request.user.id

        rom.rom_user = RomUserSchema.for_user(db_rom, user_id)
        rom.user_notes = RomUserSchema.notes_for_user(db_rom, user_id)
        rom.sibling_roms = [
            RomSchema.model_validate(r) for r in db_rom.get_sibling_roms()
        ]
        rom.user_saves = [
            SaveSchema.model_validate(s) for s in db_rom.saves if s.user_id == user_id
        ]
        rom.user_states = [
            StateSchema.model_validate(s) for s in db_rom.states if s.user_id == user_id
        ]
        rom.user_screenshots = [
            ScreenshotSchema.model_validate(s)
            for s in db_rom.screenshots
            if s.user_id == user_id
        ]
        rom.user_collections = [
            CollectionSchema.model_validate(c) for c in db_rom.get_collections(user_id)
        ]

        return rom


class UserNotesSchema(TypedDict):
    user_id: int
    username: str
    note_raw_markdown: str


class AddRomsResponse(TypedDict):
    uploaded_roms: list[str]
    skipped_roms: list[str]


class CustomStreamingResponse(StreamingResponse):
    def __init__(self, *args, **kwargs) -> None:
        self.emit_body = kwargs.pop("emit_body", None)
        super().__init__(*args, **kwargs)

    async def stream_response(self, *args, **kwargs) -> None:
        await super().stream_response(*args, **kwargs)
        await socket_handler.socket_server.emit("download:complete", self.emit_body)
