from typing import Annotated, Any

from fastapi import Depends, HTTPException, Query, Request, status
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field

from decorators.auth import protected_route
from endpoints.responses.base import BaseModel, LimitOffsetPage, PageParams
from endpoints.responses.music import (
    FacetValueSchema,
    MusicGameFacetSchema,
    MusicPlatformFacetSchema,
    MusicStatsSchema,
    MusicTrackSchema,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.auth.permissions import ResolvedPermissions
from handler.database import db_music_playlist_handler, db_rom_handler
from utils.router import APIRouter, OrderDirQuery, as_query_dependency

router = APIRouter(prefix="/music", tags=["music"])


class MusicPageParams(PageParams):
    # Sized to the largest page the jukebox requests (a whole soundtrack).
    limit: int = Field(50, ge=1, le=1_000)
    """The maximum number of items per page."""


MUSIC_PAGE_QUERY = as_query_dependency(MusicPageParams)


# Its own class so the OpenAPI schema keeps the `MusicPage_*` names.
class MusicPage[T: PydanticBaseModel](LimitOffsetPage[T]):
    pass


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
        if fid not in files or not perms.can_see_rom(files[fid].rom)
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


class MusicTrackFilters(BaseModel):
    search: str | None = None
    """Only tracks whose title, artist or album contains this text."""
    artist: str | None = None
    """Only tracks by this artist, matched exactly."""
    album: str | None = None
    """Only tracks from this album, matched exactly."""
    genre: str | None = None
    """Only tracks with this genre, matched exactly."""
    game_genre: str | None = None
    """Only tracks from games of this genre, matched exactly."""
    platform_ids: list[int] | None = None
    """Only tracks from games on these platforms."""
    year: int | None = None
    """Only tracks from this release year."""
    min_year: int | None = None
    """Only tracks from this release year or later."""
    max_year: int | None = None
    """Only tracks from this release year or earlier."""
    min_duration: float | None = None
    """Only tracks at least this long, in seconds."""
    max_duration: float | None = None
    """Only tracks at most this long, in seconds."""
    order_by: str = "title"
    """The field to sort by: `title`, `artist`, `album`, `duration`, `year`, `platform` or `added`."""
    order_dir: str = "asc"
    """The sort direction, `asc` or `desc`."""


MUSIC_TRACK_FILTERS_QUERY = as_query_dependency(MusicTrackFilters)


def _track_page(
    request: Request,
    params: MusicPageParams,
    filters: MusicTrackFilters,
    *,
    rom_id: int | None = None,
    only_favorites: bool = False,
) -> MusicPage[MusicTrackSchema]:
    perms = get_permissions(request)
    rows, total = db_rom_handler.get_music_tracks(
        visibility=perms.rom_visibility,
        **filters.model_dump(exclude={"order_by", "order_dir"}),
        rom_id=rom_id,
        order_by=filters.order_by.lower(),
        order_dir=filters.order_dir.lower(),
        limit=params.limit,
        offset=params.offset,
        is_favorite_user_id=request.user.id,
        only_favorites=only_favorites,
    )
    return MusicPage.create(
        [MusicTrackSchema.from_row(r) for r in rows], params, total=total
    )


@protected_route(router.get, "/tracks", [Scope.ROMS_READ])
def get_music_tracks(
    request: Request,
    params: Annotated[MusicPageParams, Depends(MUSIC_PAGE_QUERY)],
    filters: Annotated[MusicTrackFilters, Depends(MUSIC_TRACK_FILTERS_QUERY)],
    rom_id: Annotated[
        int | None, Query(description="Restrict to one rom's tracks.")
    ] = None,
) -> MusicPage[MusicTrackSchema]:
    """Flat, filterable, paginated list of soundtrack tracks."""
    return _track_page(request, params, filters, rom_id=rom_id)


@protected_route(router.get, "/favorites", [Scope.PLAYLISTS_READ])
def get_music_favorites(
    request: Request,
    params: Annotated[MusicPageParams, Depends(MUSIC_PAGE_QUERY)],
    filters: Annotated[MusicTrackFilters, Depends(MUSIC_TRACK_FILTERS_QUERY)],
) -> MusicPage[MusicTrackSchema]:
    """The requesting user's favorite tracks; same shape and filters as /tracks."""
    return _track_page(request, params, filters, only_favorites=True)


@protected_route(router.post, "/favorites", [Scope.PLAYLISTS_WRITE])
def add_music_favorites(
    request: Request, payload: MusicTrackIdsPayload
) -> dict[str, Any]:
    """Mark tracks as favorites; already-favorited tracks are ignored."""
    perms = get_permissions(request)
    rom_file_ids = resolve_track_ids(payload.rom_file_ids, perms)
    added = db_music_playlist_handler.add_favorite_tracks(request.user.id, rom_file_ids)
    return {"added": added}


@protected_route(router.delete, "/favorites", [Scope.PLAYLISTS_WRITE])
def remove_music_favorites(
    request: Request, payload: MusicTrackIdsPayload
) -> dict[str, Any]:
    """Unmark tracks as favorites."""
    perms = get_permissions(request)
    rom_file_ids = resolve_track_ids(payload.rom_file_ids, perms)
    removed = db_music_playlist_handler.remove_favorite_tracks(
        request.user.id, rom_file_ids
    )
    return {"removed": removed}


GenreFilterQuery = Annotated[
    str | None,
    Query(description="Only include tracks with this genre tag."),
]
GameGenreFilterQuery = Annotated[
    str | None,
    Query(description="Only include tracks from games of this genre."),
]
PlatformIdsFilterQuery = Annotated[
    list[int] | None,
    Query(
        description=(
            "Only include tracks from games on this platform. Repeat the"
            " parameter for several platforms."
        )
    ),
]
YearFilterQuery = Annotated[
    int | None,
    Query(description="Only include tracks from this year, as tagged on the file."),
]
MinYearFilterQuery = Annotated[
    int | None,
    Query(
        description=(
            "Only include tracks from this year or later, as tagged on the file."
        )
    ),
]
MaxYearFilterQuery = Annotated[
    int | None,
    Query(
        description=(
            "Only include tracks from this year or earlier, as tagged on the file."
        )
    ),
]
MinDurationFilterQuery = Annotated[
    float | None,
    Query(description="Only include tracks at least this long, in seconds."),
]
MaxDurationFilterQuery = Annotated[
    float | None,
    Query(description="Only include tracks at most this long, in seconds."),
]


def _facet_page(
    field: str,
    request: Request,
    params: PageParams,
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
    rows, total = db_rom_handler.get_music_facet(
        field=field,
        visibility=perms.rom_visibility,
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
    params: Annotated[MusicPageParams, Depends(MUSIC_PAGE_QUERY)],
    search: Annotated[str | None, Query(description="Typeahead on artist.")] = None,
    album: str | None = None,
    genre: GenreFilterQuery = None,
    platform_ids: PlatformIdsFilterQuery = None,
    year: YearFilterQuery = None,
    min_duration: MinDurationFilterQuery = None,
    max_duration: MaxDurationFilterQuery = None,
    order_by: Annotated[str, Query(description="count or value.")] = "count",
    order_dir: OrderDirQuery = "desc",
) -> MusicPage[FacetValueSchema]:
    """Distinct artists (with counts); both a browse list and a typeahead."""
    return _facet_page(
        "artists",
        request,
        params,
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
    params: Annotated[MusicPageParams, Depends(MUSIC_PAGE_QUERY)],
    search: Annotated[str | None, Query(description="Typeahead on album.")] = None,
    artist: str | None = None,
    genre: GenreFilterQuery = None,
    platform_ids: PlatformIdsFilterQuery = None,
    year: YearFilterQuery = None,
    min_duration: MinDurationFilterQuery = None,
    max_duration: MaxDurationFilterQuery = None,
    order_by: Annotated[str, Query(description="count or value.")] = "count",
    order_dir: OrderDirQuery = "desc",
) -> MusicPage[FacetValueSchema]:
    """Distinct albums (with counts); both a browse list and a typeahead."""
    return _facet_page(
        "albums",
        request,
        params,
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
    params: Annotated[MusicPageParams, Depends(MUSIC_PAGE_QUERY)],
    search: Annotated[str | None, Query(description="Typeahead on genre.")] = None,
    artist: str | None = None,
    album: str | None = None,
    platform_ids: PlatformIdsFilterQuery = None,
    year: YearFilterQuery = None,
    min_duration: MinDurationFilterQuery = None,
    max_duration: MaxDurationFilterQuery = None,
    order_by: Annotated[str, Query(description="count or value.")] = "count",
    order_dir: OrderDirQuery = "desc",
) -> MusicPage[FacetValueSchema]:
    """Distinct genres (with counts); both a browse list and a typeahead."""
    return _facet_page(
        "genres",
        request,
        params,
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
    params: Annotated[MusicPageParams, Depends(MUSIC_PAGE_QUERY)],
    search: Annotated[str | None, Query(description="Typeahead on year.")] = None,
    artist: str | None = None,
    album: str | None = None,
    genre: GenreFilterQuery = None,
    platform_ids: PlatformIdsFilterQuery = None,
    min_duration: MinDurationFilterQuery = None,
    max_duration: MaxDurationFilterQuery = None,
    order_by: Annotated[str, Query(description="count or value.")] = "count",
    order_dir: OrderDirQuery = "desc",
) -> MusicPage[FacetValueSchema]:
    """Distinct years (with counts); both a browse list and a typeahead."""
    return _facet_page(
        "years",
        request,
        params,
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


@protected_route(router.get, "/game-genres", [Scope.ROMS_READ])
def get_music_game_genres(
    request: Request,
    params: Annotated[MusicPageParams, Depends(MUSIC_PAGE_QUERY)],
    search: Annotated[
        str | None, Query(description="Typeahead on the game's genre.")
    ] = None,
    artist: str | None = None,
    album: str | None = None,
    genre: GenreFilterQuery = None,
    platform_ids: PlatformIdsFilterQuery = None,
    year: YearFilterQuery = None,
    min_year: MinYearFilterQuery = None,
    max_year: MaxYearFilterQuery = None,
    min_duration: MinDurationFilterQuery = None,
    max_duration: MaxDurationFilterQuery = None,
    order_by: Annotated[str, Query(description="count or value.")] = "count",
    order_dir: OrderDirQuery = "desc",
) -> MusicPage[FacetValueSchema]:
    """Distinct genres of the *games* the tracks belong to, with counts.

    Distinct from `/genres`, which facets the tag written on the audio file.
    """
    perms = get_permissions(request)
    rows, total = db_rom_handler.get_music_game_genre_facet(
        visibility=perms.rom_visibility,
        search=search,
        artist=artist,
        album=album,
        genre=genre,
        platform_ids=platform_ids,
        year=year,
        min_year=min_year,
        max_year=max_year,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
        limit=params.limit,
        offset=params.offset,
    )
    items = [FacetValueSchema(value=r.value, count=r.count) for r in rows]
    return MusicPage.create(items, params, total=total)


@protected_route(router.get, "/platforms", [Scope.ROMS_READ])
def get_music_platforms(
    request: Request,
    params: Annotated[MusicPageParams, Depends(MUSIC_PAGE_QUERY)],
    search: Annotated[str | None, Query(description="Typeahead on platform.")] = None,
    artist: str | None = None,
    album: str | None = None,
    genre: GenreFilterQuery = None,
    game_genre: GameGenreFilterQuery = None,
    year: YearFilterQuery = None,
    min_year: MinYearFilterQuery = None,
    max_year: MaxYearFilterQuery = None,
    min_duration: MinDurationFilterQuery = None,
    max_duration: MaxDurationFilterQuery = None,
    order_by: Annotated[str, Query(description="count or value.")] = "value",
    order_dir: OrderDirQuery = "asc",
) -> MusicPage[MusicPlatformFacetSchema]:
    """Platforms that have soundtrack tracks, with per-platform counts."""
    perms = get_permissions(request)
    rows, total = db_rom_handler.get_music_platform_facet(
        visibility=perms.rom_visibility,
        search=search,
        artist=artist,
        album=album,
        genre=genre,
        game_genre=game_genre,
        year=year,
        min_year=min_year,
        max_year=max_year,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
        limit=params.limit,
        offset=params.offset,
    )
    items = [MusicPlatformFacetSchema.from_row(r) for r in rows]
    return MusicPage.create(items, params, total=total)


@protected_route(router.get, "/games", [Scope.ROMS_READ])
def get_music_games(
    request: Request,
    params: Annotated[MusicPageParams, Depends(MUSIC_PAGE_QUERY)],
    search: Annotated[
        str | None, Query(description="Substring match on game/title/artist/album.")
    ] = None,
    artist: str | None = None,
    album: str | None = None,
    genre: GenreFilterQuery = None,
    game_genre: GameGenreFilterQuery = None,
    platform_ids: PlatformIdsFilterQuery = None,
    year: YearFilterQuery = None,
    min_year: MinYearFilterQuery = None,
    max_year: MaxYearFilterQuery = None,
    min_duration: MinDurationFilterQuery = None,
    max_duration: MaxDurationFilterQuery = None,
    order_by: Annotated[str, Query(description="count or value.")] = "value",
    order_dir: OrderDirQuery = "asc",
) -> MusicPage[MusicGameFacetSchema]:
    """Games that have soundtrack tracks -- the jukebox's album list."""
    perms = get_permissions(request)
    rows, total = db_rom_handler.get_music_game_facet(
        visibility=perms.rom_visibility,
        search=search,
        artist=artist,
        album=album,
        genre=genre,
        game_genre=game_genre,
        platform_ids=platform_ids,
        year=year,
        min_year=min_year,
        max_year=max_year,
        min_duration=min_duration,
        max_duration=max_duration,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
        limit=params.limit,
        offset=params.offset,
    )
    items = [MusicGameFacetSchema.from_row(r) for r in rows]
    return MusicPage.create(items, params, total=total)


@protected_route(router.get, "/stats", [Scope.ROMS_READ])
def get_music_stats(request: Request) -> MusicStatsSchema:
    """Library-wide track count and total duration."""
    perms = get_permissions(request)
    total, duration = db_rom_handler.get_music_stats(
        visibility=perms.rom_visibility,
    )
    return MusicStatsSchema(total_tracks=total, total_duration_seconds=duration)
