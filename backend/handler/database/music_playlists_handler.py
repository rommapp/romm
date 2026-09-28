from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import INJECTED_SESSION, begin_session
from models.music import MusicFavoriteTrack, MusicPlaylist, MusicPlaylistTrack

from .base_handler import DBBaseHandler, affected_rows


class DBMusicPlaylistsHandler(DBBaseHandler):
    @begin_session
    def add_playlist(
        self,
        playlist: MusicPlaylist,
        session: Session = INJECTED_SESSION,
    ) -> MusicPlaylist:
        playlist = session.merge(playlist)
        session.flush()

        return session.scalars(
            select(MusicPlaylist).filter_by(id=playlist.id).limit(1)
        ).one()

    @begin_session
    def get_playlist(
        self,
        id: int,
        session: Session = INJECTED_SESSION,
    ) -> MusicPlaylist | None:
        return session.scalar(select(MusicPlaylist).filter_by(id=id).limit(1))

    @begin_session
    def get_playlist_by_name(
        self,
        name: str,
        user_id: int,
        session: Session = INJECTED_SESSION,
    ) -> MusicPlaylist | None:
        return session.scalar(
            select(MusicPlaylist).filter_by(name=name, user_id=user_id).limit(1)
        )

    @begin_session
    def get_playlists(
        self,
        user_id: int,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[MusicPlaylist]:
        """The user's own playlists plus other users' public ones."""
        return (
            session.scalars(
                select(MusicPlaylist)
                .where(
                    or_(
                        MusicPlaylist.user_id == user_id,
                        MusicPlaylist.is_public.is_(True),
                    )
                )
                .order_by(MusicPlaylist.name.asc())
            )
            .unique()
            .all()
        )

    @begin_session
    def update_playlist(
        self,
        id: int,
        data: dict[str, Any],
        session: Session = INJECTED_SESSION,
    ) -> MusicPlaylist:
        session.execute(
            update(MusicPlaylist)
            .where(MusicPlaylist.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

        return session.scalars(select(MusicPlaylist).filter_by(id=id).limit(1)).one()

    @begin_session
    def delete_playlist(
        self,
        id: int,
        session: Session = INJECTED_SESSION,
    ) -> None:
        session.execute(
            delete(MusicPlaylist)
            .where(MusicPlaylist.id == id)
            .execution_options(synchronize_session="evaluate")
        )

    @begin_session
    def get_playlist_track_counts(
        self,
        playlist_ids: Sequence[int],
        session: Session = INJECTED_SESSION,
    ) -> dict[int, int]:
        """Stored entry counts per playlist, before any visibility filtering."""
        if not playlist_ids:
            return {}
        rows = session.execute(
            select(MusicPlaylistTrack.playlist_id, func.count())
            .where(MusicPlaylistTrack.playlist_id.in_(playlist_ids))
            .group_by(MusicPlaylistTrack.playlist_id)
        ).all()
        return {playlist_id: count for playlist_id, count in rows}

    @begin_session
    def get_playlist_entries(
        self,
        playlist_id: int,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[MusicPlaylistTrack]:
        return session.scalars(
            select(MusicPlaylistTrack)
            .filter_by(playlist_id=playlist_id)
            .order_by(MusicPlaylistTrack.position.asc(), MusicPlaylistTrack.id.asc())
        ).all()

    @begin_session
    def add_tracks_to_playlist(
        self,
        playlist_id: int,
        track_ids: Sequence[int],
        session: Session = INJECTED_SESSION,
    ) -> int:
        candidates = list(dict.fromkeys(track_ids))
        if not candidates:
            return 0
        existing = set(
            session.scalars(
                select(MusicPlaylistTrack.track_id).where(
                    MusicPlaylistTrack.playlist_id == playlist_id,
                    MusicPlaylistTrack.track_id.in_(candidates),
                )
            )
        )
        new_entries = [e for e in candidates if e not in existing]
        if not new_entries:
            return 0

        next_position = (
            session.scalar(
                select(func.max(MusicPlaylistTrack.position)).where(
                    MusicPlaylistTrack.playlist_id == playlist_id
                )
            )
            or 0
        ) + 1
        added = 0
        for track_id in new_entries:
            try:
                with session.begin_nested():
                    session.execute(
                        insert(MusicPlaylistTrack).values(
                            playlist_id=playlist_id,
                            track_id=track_id,
                            position=next_position + added,
                        )
                    )
            except IntegrityError:
                continue
            added += 1
        if added:
            self._touch(playlist_id, session)
        return added

    @begin_session
    def remove_tracks_from_playlist(
        self,
        playlist_id: int,
        track_ids: Sequence[int],
        session: Session = INJECTED_SESSION,
    ) -> int:
        if not track_ids:
            return 0
        result = session.execute(
            delete(MusicPlaylistTrack).where(
                MusicPlaylistTrack.playlist_id == playlist_id,
                MusicPlaylistTrack.track_id.in_(list(track_ids)),
            )
        )
        if affected_rows(result) > 0:
            self._touch(playlist_id, session)
        return affected_rows(result)

    @begin_session
    def set_playlist_track_order(
        self,
        playlist_id: int,
        ordered_entry_ids: Sequence[int],
        session: Session = INJECTED_SESSION,
    ) -> None:
        """Rewrite positions to match ordered_entry_ids; entries not listed keep
        their relative order after the listed ones."""
        entries = session.scalars(
            select(MusicPlaylistTrack)
            .filter_by(playlist_id=playlist_id)
            .order_by(MusicPlaylistTrack.position.asc(), MusicPlaylistTrack.id.asc())
        ).all()
        by_id = {e.id: e for e in entries}
        ordered_ids = set(ordered_entry_ids)
        ordered = [by_id[eid] for eid in ordered_entry_ids if eid in by_id]
        remaining = [e for e in entries if e.id not in ordered_ids]
        for position, entry in enumerate(ordered + remaining):
            entry.position = position
        session.flush()
        self._touch(playlist_id, session)

    @begin_session
    def add_favorite_tracks(
        self,
        user_id: int,
        track_ids: Sequence[int],
        session: Session = INJECTED_SESSION,
    ) -> int:
        candidates = list(dict.fromkeys(track_ids))
        if not candidates:
            return 0
        existing = set(
            session.scalars(
                select(MusicFavoriteTrack.track_id).where(
                    MusicFavoriteTrack.user_id == user_id,
                    MusicFavoriteTrack.track_id.in_(candidates),
                )
            )
        )
        new_entries = [e for e in candidates if e not in existing]
        if not new_entries:
            return 0
        added = 0
        for track_id in new_entries:
            try:
                with session.begin_nested():
                    session.execute(
                        insert(MusicFavoriteTrack).values(
                            user_id=user_id, track_id=track_id
                        )
                    )
            except IntegrityError:
                continue
            added += 1
        return added

    @begin_session
    def remove_favorite_tracks(
        self,
        user_id: int,
        track_ids: Sequence[int],
        session: Session = INJECTED_SESSION,
    ) -> int:
        if not track_ids:
            return 0
        result = session.execute(
            delete(MusicFavoriteTrack).where(
                MusicFavoriteTrack.user_id == user_id,
                MusicFavoriteTrack.track_id.in_(list(track_ids)),
            )
        )
        return affected_rows(result)

    @staticmethod
    def _touch(playlist_id: int, session: Session) -> None:
        session.execute(
            update(MusicPlaylist)
            .where(MusicPlaylist.id == playlist_id)
            .values(updated_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session="evaluate")
        )
