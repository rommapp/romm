from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict

from config import FRONTEND_RESOURCES_PATH

from .base import UTCDatetime


class MusicTrackSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rom_file_id: int
    rom_id: int
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    year: int | None = None
    track: int | None = None
    disc: int | None = None
    duration_seconds: float | None = None
    has_embedded_cover: bool = False
    md5_hash: str | None = None
    is_favorite: bool = False
    game_name: str | None = None
    platform_id: int
    platform_slug: str
    platform_name: str
    stream_url: str
    cover_url: str | None = None

    @classmethod
    def from_row(cls, row: Any) -> MusicTrackSchema:
        if row.cover_path:
            cover_url = f"{FRONTEND_RESOURCES_PATH}/{row.cover_path}"
        elif row.path_cover_l:
            cover_url = f"{FRONTEND_RESOURCES_PATH}/{row.path_cover_l}"
        else:
            cover_url = None
        return cls(
            rom_file_id=row.rom_file_id,
            rom_id=row.rom_id,
            title=row.title,
            artist=row.artist,
            album=row.album,
            genre=row.genre,
            year=row.year,
            track=row.track,
            disc=row.disc,
            duration_seconds=row.duration_seconds,
            has_embedded_cover=row.has_embedded_cover,
            md5_hash=row.md5_hash or None,
            is_favorite=bool(row.is_favorite),
            game_name=row.game_name,
            platform_id=row.platform_id,
            platform_slug=row.platform_slug,
            platform_name=row.platform_name,
            stream_url=f"/api/roms/{row.rom_file_id}/files/content/{quote(row.file_name)}",
            cover_url=cover_url,
        )


class FacetValueSchema(BaseModel):
    """A distinct value of a track field plus how many tracks carry it."""

    value: str | int
    count: int


class MusicPlaylistSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    is_public: bool = False
    user_id: int
    owner_username: str
    track_count: int = 0
    created_at: UTCDatetime
    updated_at: UTCDatetime
