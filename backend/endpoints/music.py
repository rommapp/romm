from typing import Annotated, Any
from urllib.parse import quote

from fastapi import Query, Request
from fastapi_pagination import resolve_params
from fastapi_pagination.limit_offset import LimitOffsetPage, LimitOffsetParams
from pydantic import BaseModel

from config import FRONTEND_RESOURCES_PATH
from decorators.auth import protected_route
from endpoints.responses.music import FacetValueSchema, MusicTrackSchema
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.database import db_rom_handler
from utils.router import APIRouter

router = APIRouter(prefix="/music", tags=["music"])


class MusicLimitOffsetParams(LimitOffsetParams):
    limit: int = Query(50, ge=1, le=10_000, description="Page size limit")
    offset: int = Query(0, ge=0, description="Page offset")


class MusicPage[T: BaseModel](LimitOffsetPage[T]):
    __params_type__ = MusicLimitOffsetParams


def _track_to_schema(row: Any) -> MusicTrackSchema:
    if row.cover_path:
        cover_url = f"{FRONTEND_RESOURCES_PATH}/{row.cover_path}"
    elif row.path_cover_l:
        cover_url = f"{FRONTEND_RESOURCES_PATH}/{row.path_cover_l}"
    else:
        cover_url = None
    return MusicTrackSchema(
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
        game_name=row.game_name,
        platform_id=row.platform_id,
        platform_slug=row.platform_slug,
        platform_name=row.platform_name,
        stream_url=f"/api/roms/{row.rom_file_id}/files/content/{quote(row.file_name)}",
        cover_url=cover_url,
    )


@protected_route(router.get, "/tracks", [Scope.ROMS_READ])
def get_music_tracks(
    request: Request,
    search: Annotated[
        str | None, Query(description="Substring match on title/artist/album.")
    ] = None,
    artist: Annotated[str | None, Query(description="Exact artist.")] = None,
    album: Annotated[str | None, Query(description="Exact album.")] = None,
    genre: Annotated[str | None, Query(description="Exact genre.")] = None,
    platform_ids: Annotated[
        list[int] | None, Query(description="Restrict to these platform ids.")
    ] = None,
    year: Annotated[int | None, Query(description="Exact release year.")] = None,
    min_duration: Annotated[
        float | None, Query(description="Minimum duration in seconds.")
    ] = None,
    max_duration: Annotated[
        float | None, Query(description="Maximum duration in seconds.")
    ] = None,
    order_by: Annotated[
        str,
        Query(description="title/artist/album/duration/year/platform/added."),
    ] = "title",
    order_dir: Annotated[str, Query(description="asc or desc.")] = "asc",
) -> MusicPage[MusicTrackSchema]:
    """Flat, filterable, paginated list of soundtrack tracks."""
    perms = get_permissions(request)
    params = resolve_params()
    rows, total = db_rom_handler.get_music_tracks(
        hidden_platform_ids=perms.hidden_platform_ids,
        hidden_rom_ids=perms.hidden_rom_ids,
        search=search,
        artist=artist,
        album=album,
        genre=genre,
        platform_ids=platform_ids,
        year=year,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
        limit=params.limit,
        offset=params.offset,
    )
    return MusicPage.create([_track_to_schema(r) for r in rows], params, total=total)


def _facet_page(
    field: str,
    request: Request,
    *,
    search: str | None,
    artist: str | None,
    album: str | None,
    genre: str | None,
    platform_ids: list[int] | None,
    year: int | None,
    min_duration: float | None,
    max_duration: float | None,
    order_by: str,
    order_dir: str,
) -> MusicPage[FacetValueSchema]:
    perms = get_permissions(request)
    params = resolve_params()
    rows, total = db_rom_handler.get_music_facet(
        field=field,
        hidden_platform_ids=perms.hidden_platform_ids,
        hidden_rom_ids=perms.hidden_rom_ids,
        search=search,
        artist=artist,
        album=album,
        genre=genre,
        platform_ids=platform_ids,
        year=year,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
        limit=params.limit,
        offset=params.offset,
    )
    items = [FacetValueSchema(value=r.value, count=r.count) for r in rows]
    return MusicPage.create(items, params, total=total)


@protected_route(router.get, "/artists", [Scope.ROMS_READ])
def get_music_artists(
    request: Request,
    search: Annotated[str | None, Query(description="Typeahead on artist.")] = None,
    album: Annotated[str | None, Query()] = None,
    genre: Annotated[str | None, Query()] = None,
    platform_ids: Annotated[list[int] | None, Query()] = None,
    year: Annotated[int | None, Query()] = None,
    min_duration: Annotated[float | None, Query()] = None,
    max_duration: Annotated[float | None, Query()] = None,
    order_by: Annotated[str, Query(description="count or value.")] = "count",
    order_dir: Annotated[str, Query()] = "desc",
) -> MusicPage[FacetValueSchema]:
    """Distinct artists (with counts); both a browse list and a typeahead."""
    return _facet_page(
        "artists",
        request,
        search=search,
        artist=None,
        album=album,
        genre=genre,
        platform_ids=platform_ids,
        year=year,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by,
        order_dir=order_dir,
    )


@protected_route(router.get, "/albums", [Scope.ROMS_READ])
def get_music_albums(
    request: Request,
    search: Annotated[str | None, Query(description="Typeahead on album.")] = None,
    artist: Annotated[str | None, Query()] = None,
    genre: Annotated[str | None, Query()] = None,
    platform_ids: Annotated[list[int] | None, Query()] = None,
    year: Annotated[int | None, Query()] = None,
    min_duration: Annotated[float | None, Query()] = None,
    max_duration: Annotated[float | None, Query()] = None,
    order_by: Annotated[str, Query(description="count or value.")] = "count",
    order_dir: Annotated[str, Query()] = "desc",
) -> MusicPage[FacetValueSchema]:
    """Distinct albums (with counts); both a browse list and a typeahead."""
    return _facet_page(
        "albums",
        request,
        search=search,
        artist=artist,
        album=None,
        genre=genre,
        platform_ids=platform_ids,
        year=year,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by,
        order_dir=order_dir,
    )


@protected_route(router.get, "/genres", [Scope.ROMS_READ])
def get_music_genres(
    request: Request,
    search: Annotated[str | None, Query(description="Typeahead on genre.")] = None,
    artist: Annotated[str | None, Query()] = None,
    album: Annotated[str | None, Query()] = None,
    platform_ids: Annotated[list[int] | None, Query()] = None,
    year: Annotated[int | None, Query()] = None,
    min_duration: Annotated[float | None, Query()] = None,
    max_duration: Annotated[float | None, Query()] = None,
    order_by: Annotated[str, Query(description="count or value.")] = "count",
    order_dir: Annotated[str, Query()] = "desc",
) -> MusicPage[FacetValueSchema]:
    """Distinct genres (with counts); both a browse list and a typeahead."""
    return _facet_page(
        "genres",
        request,
        search=search,
        artist=artist,
        album=album,
        genre=None,
        platform_ids=platform_ids,
        year=year,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by,
        order_dir=order_dir,
    )


@protected_route(router.get, "/years", [Scope.ROMS_READ])
def get_music_years(
    request: Request,
    search: Annotated[str | None, Query(description="Typeahead on year.")] = None,
    artist: Annotated[str | None, Query()] = None,
    album: Annotated[str | None, Query()] = None,
    genre: Annotated[str | None, Query()] = None,
    platform_ids: Annotated[list[int] | None, Query()] = None,
    min_duration: Annotated[float | None, Query()] = None,
    max_duration: Annotated[float | None, Query()] = None,
    order_by: Annotated[str, Query(description="count or value.")] = "count",
    order_dir: Annotated[str, Query()] = "desc",
) -> MusicPage[FacetValueSchema]:
    """Distinct years (with counts); both a browse list and a typeahead."""
    return _facet_page(
        "years",
        request,
        search=search,
        artist=artist,
        album=album,
        genre=genre,
        platform_ids=platform_ids,
        year=None,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by,
        order_dir=order_dir,
    )
