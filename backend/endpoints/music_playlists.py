from typing import Annotated

from fastapi import HTTPException
from fastapi import Path as PathVar
from fastapi import Query, Request, Response, status
from fastapi_pagination import resolve_params
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from decorators.auth import protected_route
from endpoints.music import (
    MusicPage,
    MusicTrackIdsPayload,
    resolve_track_refs,
)
from endpoints.responses.music import MusicPlaylistSchema, MusicTrackSchema
from exceptions.endpoint_exceptions import (
    MusicPlaylistAlreadyExistsException,
    MusicPlaylistNotFoundException,
    MusicPlaylistPermissionError,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.database import db_music_playlist_handler, db_rom_handler
from models.music import MusicPlaylist
from utils.router import APIRouter

router = APIRouter(prefix="/music/playlists", tags=["music"])

PLAYLIST_NAME_MAX_LENGTH = 400


class MusicPlaylistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=PLAYLIST_NAME_MAX_LENGTH)
    description: str | None = None
    is_public: bool = False


class MusicPlaylistUpdateRequest(BaseModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=PLAYLIST_NAME_MAX_LENGTH
    )
    description: str | None = None
    is_public: bool | None = None


def _playlist_schema(playlist: MusicPlaylist, track_count: int) -> MusicPlaylistSchema:
    schema = MusicPlaylistSchema.model_validate(playlist)
    return schema.model_copy(update={"track_count": track_count})


def _get_visible_playlist(request: Request, id: int) -> MusicPlaylist:
    playlist = db_music_playlist_handler.get_playlist(id)
    if not playlist:
        raise MusicPlaylistNotFoundException(id)
    if playlist.user_id != request.user.id and not playlist.is_public:
        raise MusicPlaylistPermissionError(id)
    return playlist


def _get_owned_playlist(request: Request, id: int) -> MusicPlaylist:
    playlist = db_music_playlist_handler.get_playlist(id)
    if not playlist:
        raise MusicPlaylistNotFoundException(id)
    if playlist.user_id != request.user.id:
        raise MusicPlaylistPermissionError(id)
    return playlist


@protected_route(router.get, "", [Scope.PLAYLISTS_READ])
def get_playlists(request: Request) -> list[MusicPlaylistSchema]:
    """The requesting user's playlists plus other users' public playlists."""
    playlists = db_music_playlist_handler.get_playlists(request.user.id)
    counts = db_music_playlist_handler.get_playlist_track_counts(
        [p.id for p in playlists]
    )
    return [_playlist_schema(p, counts.get(p.id, 0)) for p in playlists]


@protected_route(router.post, "", [Scope.PLAYLISTS_WRITE])
def add_playlist(
    request: Request, payload: MusicPlaylistCreateRequest
) -> MusicPlaylistSchema:
    if db_music_playlist_handler.get_playlist_by_name(payload.name, request.user.id):
        raise MusicPlaylistAlreadyExistsException(payload.name)
    try:
        playlist = db_music_playlist_handler.add_playlist(
            MusicPlaylist(
                name=payload.name,
                description=payload.description,
                is_public=payload.is_public,
                user_id=request.user.id,
            )
        )
    except IntegrityError:
        raise MusicPlaylistAlreadyExistsException(payload.name) from None
    return _playlist_schema(playlist, 0)


@protected_route(router.get, "/{id}", [Scope.PLAYLISTS_READ])
def get_playlist(
    request: Request,
    id: Annotated[int, PathVar(description="Playlist internal id.", ge=1)],
) -> MusicPlaylistSchema:
    playlist = _get_visible_playlist(request, id)
    counts = db_music_playlist_handler.get_playlist_track_counts([playlist.id])
    return _playlist_schema(playlist, counts.get(playlist.id, 0))


@protected_route(router.put, "/{id}", [Scope.PLAYLISTS_WRITE])
def update_playlist(
    request: Request,
    id: Annotated[int, PathVar(description="Playlist internal id.", ge=1)],
    payload: MusicPlaylistUpdateRequest,
) -> MusicPlaylistSchema:
    playlist = _get_owned_playlist(request, id)
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "description" in payload.model_fields_set:
        data["description"] = payload.description
    if (
        "name" in data
        and data["name"] != playlist.name
        and db_music_playlist_handler.get_playlist_by_name(
            data["name"], request.user.id
        )
    ):
        raise MusicPlaylistAlreadyExistsException(data["name"])
    if data:
        try:
            playlist = db_music_playlist_handler.update_playlist(id, data)
        except IntegrityError:
            raise MusicPlaylistAlreadyExistsException(data.get("name")) from None
    counts = db_music_playlist_handler.get_playlist_track_counts([id])
    return _playlist_schema(playlist, counts.get(id, 0))


@protected_route(router.delete, "/{id}", [Scope.PLAYLISTS_WRITE])
def delete_playlist(
    request: Request,
    id: Annotated[int, PathVar(description="Playlist internal id.", ge=1)],
) -> Response:
    _get_owned_playlist(request, id)
    db_music_playlist_handler.delete_playlist(id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@protected_route(router.get, "/{id}/tracks", [Scope.PLAYLISTS_READ])
def get_playlist_tracks(
    request: Request,
    id: Annotated[int, PathVar(description="Playlist internal id.", ge=1)],
    order_by: Annotated[
        str,
        Query(description="position/title/artist/album/duration/year/platform."),
    ] = "position",
    order_dir: Annotated[str, Query(description="asc or desc.")] = "asc",
) -> MusicPage[MusicTrackSchema]:
    """Resolvable tracks of a playlist, in playlist order by default.

    Entries whose file is gone (or hidden from the viewer) are omitted, so the
    page total can be lower than the playlist's stored track_count."""
    playlist = _get_visible_playlist(request, id)
    perms = get_permissions(request)
    params = resolve_params()
    rows, total = db_rom_handler.get_music_tracks(
        hidden_platform_ids=perms.hidden_platform_ids,
        hidden_rom_ids=perms.hidden_rom_ids,
        order_by=order_by.lower(),
        order_dir=order_dir.lower(),
        limit=params.limit,
        offset=params.offset,
        is_favorite_user_id=request.user.id,
        playlist_id=playlist.id,
    )
    return MusicPage.create(
        [MusicTrackSchema.from_row(r) for r in rows], params, total=total
    )


@protected_route(router.post, "/{id}/tracks", [Scope.PLAYLISTS_WRITE])
def add_playlist_tracks(
    request: Request,
    id: Annotated[int, PathVar(description="Playlist internal id.", ge=1)],
    payload: MusicTrackIdsPayload,
) -> dict:
    """Append tracks to the playlist; tracks already present are ignored."""
    playlist = _get_owned_playlist(request, id)
    perms = get_permissions(request)
    refs = resolve_track_refs(payload.rom_file_ids, perms)
    added = db_music_playlist_handler.add_tracks_to_playlist(playlist.id, refs)
    return {"added": added}


@protected_route(router.delete, "/{id}/tracks", [Scope.PLAYLISTS_WRITE])
def remove_playlist_tracks(
    request: Request,
    id: Annotated[int, PathVar(description="Playlist internal id.", ge=1)],
    payload: MusicTrackIdsPayload,
) -> dict:
    playlist = _get_owned_playlist(request, id)
    perms = get_permissions(request)
    refs = resolve_track_refs(payload.rom_file_ids, perms)
    removed = db_music_playlist_handler.remove_tracks_from_playlist(playlist.id, refs)
    return {"removed": removed}


@protected_route(router.put, "/{id}/tracks/order", [Scope.PLAYLISTS_WRITE])
def set_playlist_track_order(
    request: Request,
    id: Annotated[int, PathVar(description="Playlist internal id.", ge=1)],
    payload: MusicTrackIdsPayload,
) -> Response:
    """Reorder the playlist to match the given rom_file_ids.

    Entries not covered by the payload (including dangling ones) keep their
    relative order after the listed tracks."""
    playlist = _get_owned_playlist(request, id)
    perms = get_permissions(request)
    refs = resolve_track_refs(payload.rom_file_ids, perms)
    entries = db_music_playlist_handler.get_playlist_entries(playlist.id)
    entry_by_ref = {(e.rom_id, e.md5_hash): e.id for e in entries}
    if any(ref not in entry_by_ref for ref in refs):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload contains tracks that are not in the playlist",
        )
    ordered_entry_ids = [entry_by_ref[ref] for ref in refs]
    db_music_playlist_handler.set_playlist_track_order(playlist.id, ordered_entry_ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
