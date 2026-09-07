from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

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
    is_favorite: bool = False
    game_name: str | None = None
    game_genres: list[str] = Field(default_factory=list)
    added_at: UTCDatetime
    platform_id: int
    platform_slug: str
    platform_name: str
    stream_url: str
    cover_url: str | None = None
    game_cover_url: str | None = None

    @staticmethod
    def cover_url_for(cover_path: str | None, rom_cover_path: str | None) -> str | None:
        """The track's artwork, in priority order: its own embedded cover, then
        the game's cover art. None lets the frontend fall back."""
        resource = cover_path or rom_cover_path
        return f"{FRONTEND_RESOURCES_PATH}/{resource}" if resource else None

    @classmethod
    def from_row(cls, row: Any) -> MusicTrackSchema:
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
            is_favorite=bool(row.is_favorite),
            game_name=row.game_name,
            game_genres=row.game_genres or [],
            added_at=row.added_at,
            platform_id=row.platform_id,
            platform_slug=row.platform_slug,
            platform_name=row.platform_name,
            stream_url=f"/api/roms/{row.rom_file_id}/files/content/{quote(row.file_name)}",
            cover_url=cls.cover_url_for(row.cover_path, row.path_cover_l),
            game_cover_url=cls.cover_url_for(None, row.path_cover_l),
        )


class FacetValueSchema(BaseModel):
    """A distinct value of a track field plus how many tracks carry it."""

    value: str | int
    count: int


class MusicStatsSchema(BaseModel):
    """Library-wide soundtrack totals."""

    total_tracks: int
    total_duration_seconds: float


class MusicPlatformFacetSchema(BaseModel):
    """A platform that has soundtrack tracks, plus how many it has."""

    id: int
    slug: str
    name: str
    count: int

    @classmethod
    def from_row(cls, row: Any) -> MusicPlatformFacetSchema:
        return cls(id=row.id, slug=row.slug, name=row.name, count=row.count)


class MusicGameFacetSchema(BaseModel):
    """A game that has soundtrack tracks -- one entry of the album list."""

    rom_id: int
    name: str
    platform_id: int
    platform_slug: str
    platform_name: str
    cover_url: str | None = None
    count: int

    @classmethod
    def from_row(cls, row: Any) -> MusicGameFacetSchema:
        return cls(
            rom_id=row.rom_id,
            name=row.name,
            platform_id=row.platform_id,
            platform_slug=row.platform_slug,
            platform_name=row.platform_name,
            cover_url=MusicTrackSchema.cover_url_for(None, row.path_cover_l),
            count=row.count,
        )


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
