import re
from typing import Optional

from endpoints.responses.assets import SaveSchema, ScreenshotSchema, StateSchema
from fastapi import Request
from fastapi.responses import StreamingResponse
from handler import socket_handler
from handler.igdb_handler import IGDBRelatedGame
from pydantic import BaseModel, computed_field, Field
from models.rom import Rom
from typing_extensions import TypedDict, NotRequired


SORT_COMPARE_REGEX = r"^([Tt]he|[Aa]|[Aa]nd)\s"


class RomMetadata(TypedDict):
    expansions: NotRequired[list[IGDBRelatedGame]]
    dlcs: NotRequired[list[IGDBRelatedGame]]
    remasters: NotRequired[list[IGDBRelatedGame]]
    remakes: NotRequired[list[IGDBRelatedGame]]
    expanded_games: NotRequired[list[IGDBRelatedGame]]
    ports: NotRequired[list[IGDBRelatedGame]]
    similar_games: NotRequired[list[IGDBRelatedGame]]


class RomSchema(BaseModel):
    id: int
    igdb_id: Optional[int]
    sgdb_id: Optional[int]

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
    total_rating: Optional[str]
    aggregated_rating: Optional[str]
    first_release_date: Optional[int]
    alternative_names: list[str]
    genres: list[str]
    franchises: list[str]
    collections: list[str]
    companies: list[str]
    game_modes: list[str]
    igdb_metadata: Optional[RomMetadata]

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
    url_screenshots: list[str]
    merged_screenshots: list[str]
    full_path: str

    sibling_roms: list["RomSchema"] = Field(default_factory=list)
    user_saves: list[SaveSchema] = Field(default_factory=list)
    user_states: list[StateSchema] = Field(default_factory=list)
    user_screenshots: list[ScreenshotSchema] = Field(default_factory=list)

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

    @classmethod
    def from_orm_with_request(cls, db_rom: Rom, request: Request) -> "RomSchema":
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
