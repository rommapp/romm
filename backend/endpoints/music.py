from typing import Annotated

from fastapi import HTTPException, Query, Request, status
from fastapi_pagination import resolve_params
from fastapi_pagination.limit_offset import LimitOffsetPage, LimitOffsetParams
from pydantic import BaseModel

from decorators.auth import protected_route
from endpoints.responses.music import FacetValueSchema, MusicTrackSchema
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.auth.permissions import ResolvedPermissions
from handler.database import db_music_playlist_handler, db_rom_handler
from utils.router import APIRouter

router = APIRouter(prefix="/music", tags=["music"])


class MusicLimitOffsetParams(LimitOffsetParams):
    limit: int = Query(50, ge=1, le=10_000, description="Page size limit")
    offset: int = Query(0, ge=0, description="Page offset")


class MusicPage[T: BaseModel](LimitOffsetPage[T]):
    __params_type__ = MusicLimitOffsetParams


class MusicTrackIdsPayload(BaseModel):
    rom_file_ids: list[int]


def resolve_track_ids(rom_file_ids: list[int], perms: ResolvedPermissions) -> list[int]:
    """Validate rom_file ids as music tracks the requester may see.

    Raises 400 when any id does not point to a visible music track; hidden and
    missing files get the same message so existence is not leaked."""
    files = {
        f.id: f
        for f in db_rom_handler.get_rom_files_by_ids(list(dict.fromkeys(rom_file_ids)))
    }
    missing = [
        fid
        for fid in rom_file_ids
        if fid not in files
        or not perms.can_see_rom(files[fid].rom_id, files[fid].rom.platform_id)
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tracks not found: {sorted(set(missing))}",
        )
    not_tracks = [fid for fid in rom_file_ids if not files[fid].track_meta]
    if not_tracks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Files are not music tracks: {sorted(set(not_tracks))}",
        )
    return list(dict.fromkeys(rom_file_ids))


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
    rom_id: Annotated[
        int | None, Query(description="Restrict to one rom's tracks.")
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
        rom_id=rom_id,
        year=year,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
        limit=params.limit,
        offset=params.offset,
        is_favorite_user_id=request.user.id,
    )
    return MusicPage.create(
        [MusicTrackSchema.from_row(r) for r in rows], params, total=total
    )


@protected_route(router.get, "/favorites", [Scope.PLAYLISTS_READ])
def get_music_favorites(
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
    """The requesting user's favorite tracks; same shape and filters as /tracks."""
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
        is_favorite_user_id=request.user.id,
        only_favorites=True,
    )
    return MusicPage.create(
        [MusicTrackSchema.from_row(r) for r in rows], params, total=total
    )


@protected_route(router.post, "/favorites", [Scope.PLAYLISTS_WRITE])
def add_music_favorites(request: Request, payload: MusicTrackIdsPayload) -> dict:
    """Mark tracks as favorites; already-favorited tracks are ignored."""
    perms = get_permissions(request)
    rom_file_ids = resolve_track_ids(payload.rom_file_ids, perms)
    added = db_music_playlist_handler.add_favorite_tracks(request.user.id, rom_file_ids)
    return {"added": added}


@protected_route(router.delete, "/favorites", [Scope.PLAYLISTS_WRITE])
def remove_music_favorites(request: Request, payload: MusicTrackIdsPayload) -> dict:
    """Unmark tracks as favorites."""
    perms = get_permissions(request)
    rom_file_ids = resolve_track_ids(payload.rom_file_ids, perms)
    removed = db_music_playlist_handler.remove_favorite_tracks(
        request.user.id, rom_file_ids
    )
    return {"removed": removed}


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
