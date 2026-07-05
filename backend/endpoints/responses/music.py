from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
    game_name: str | None = None
    platform_id: int
    platform_slug: str
    platform_name: str
    stream_url: str
    cover_url: str | None = None


class FacetValueSchema(BaseModel):
    """A distinct value of a track field plus how many tracks carry it."""

    value: str | int
    count: int
