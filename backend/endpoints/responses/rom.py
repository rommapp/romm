import re
from datetime import datetime
from typing import Optional, get_type_hints
from typing_extensions import TypedDict, NotRequired

from endpoints.responses.assets import SaveSchema, ScreenshotSchema, StateSchema
from fastapi import Request
from fastapi.responses import StreamingResponse
from handler.socket_handler import socket_handler
from handler.metadata.igdb_handler import IGDBMetadata
from handler.metadata.moby_handler import MobyMetadata
from pydantic import BaseModel, computed_field, Field
from models.rom import Rom


SORT_COMPARE_REGEX = r"^([Tt]he|[Aa]|[Aa]nd)\s"

RomIGDBMetadata = TypedDict(
    "RomIGDBMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(IGDBMetadata).items()},
    total=False,
)
RomMobyMetadata = TypedDict(
    "RomMobyMetadata",
    {k: NotRequired[v] for k, v in get_type_hints(MobyMetadata).items()},
    total=False,
)


class RomNoteSchema(BaseModel):
    id: int
    user_id: int
    rom_id: int
    last_edited_at: datetime
    raw_markdown: str
    is_public: bool
    user__username: str

    class Config:
        from_attributes = True

    @classmethod
    def for_user(cls, db_rom: Rom, user_id: int) -> list["RomNoteSchema"]:
        return [
            cls.model_validate(n)
            for n in db_rom.notes
            # This is what filters out private notes
            if n.user_id == user_id or n.is_public
        ]


class RomSchema(BaseModel):
    id: int
    igdb_id: Optional[int]
    sgdb_id: Optional[int]
    moby_id: Optional[int]

    platform_id: int
    platform_slug: str
    platform_name: str

    file_name: str
    file_name_no_tags: str
    file_name_no_ext: str
    file_extension: str
    file_path: str
    file_size_bytes: int

    name: Optional[str]
    slug: Optional[str]
    summary: Optional[str]

    # Metadata fields
    first_release_date: Optional[int]
    alternative_names: list[str]
    genres: list[str]
    franchises: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
    igdb_metadata: Optional[RomIGDBMetadata]
    moby_metadata: Optional[RomMobyMetadata]

    path_cover_s: Optional[str]
    path_cover_l: Optional[str]
    has_cover: bool
    url_cover: Optional[str]

    revision: Optional[str]
    regions: list[str]
    languages: list[str]
    tags: list[str]

    multi: bool
    files: list[str]
    full_path: str

    class Config:
        from_attributes = True

    @computed_field
    @property
    def sort_comparator(self) -> str:
        return (
            re.sub(
                SORT_COMPARE_REGEX,
                "",
                self.name or self.file_name_no_tags,
            )
            .strip()
            .lower()
        )


class UserRomSchema(RomSchema):
    merged_screenshots: list[str]
    sibling_roms: list["RomSchema"] = Field(default_factory=list)
    user_saves: list[SaveSchema] = Field(default_factory=list)
    user_states: list[StateSchema] = Field(default_factory=list)
    user_screenshots: list[ScreenshotSchema] = Field(default_factory=list)
    user_notes: list[RomNoteSchema] = Field(default_factory=list)

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> "UserRomSchema":
        rom = cls.model_validate(db_rom)
        user_id = request.user.id

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
        rom.user_notes = RomNoteSchema.for_user(db_rom, user_id)

        return rom


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
