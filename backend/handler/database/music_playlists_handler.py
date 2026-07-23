from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.music import MusicFavoriteTrack, MusicPlaylist, MusicPlaylistTrack

from .base_handler import DBBaseHandler

# A track reference is (rom_id, md5_hash); see models/music.py for why files
# are not referenced by rom_file_id.
TrackRef = tuple[int, str]


class DBMusicPlaylistsHandler(DBBaseHandler):
    @begin_session
    def add_playlist(
        self,
        playlist: MusicPlaylist,
        session: Session = None,  # type: ignore
    ) -> MusicPlaylist:
        playlist = session.merge(playlist)
        session.flush()

        return session.scalar(select(MusicPlaylist).filter_by(id=playlist.id).limit(1))

    @begin_session
    def get_playlist(
        self,
        id: int,
        session: Session = None,  # type: ignore
    ) -> MusicPlaylist | None:
        return session.scalar(select(MusicPlaylist).filter_by(id=id).limit(1))

    @begin_session
    def get_playlist_by_name(
        self,
        name: str,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> MusicPlaylist | None:
        return session.scalar(
            select(MusicPlaylist).filter_by(name=name, user_id=user_id).limit(1)
        )

    @begin_session
    def get_playlists(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
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
        data: dict,
        session: Session = None,  # type: ignore
    ) -> MusicPlaylist:
        session.execute(
            update(MusicPlaylist)
            .where(MusicPlaylist.id == id)
            .values(**data)
            .execution_options(synchronize_session="evaluate")
        )

        return session.scalar(select(MusicPlaylist).filter_by(id=id).limit(1))

    @begin_session
    def delete_playlist(
        self,
        id: int,
        session: Session = None,  # type: ignore
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
        session: Session = None,  # type: ignore
    ) -> dict[int, int]:
        """Stored entry counts per playlist (dangling entries included)."""
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
        session: Session = None,  # type: ignore
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
        entries: Sequence[TrackRef],
        session: Session = None,  # type: ignore
    ) -> int:
        candidates = list(dict.fromkeys(entries))
        if not candidates:
            return 0
        existing = {
            (rom_id, md5)
            for rom_id, md5 in session.execute(
                select(MusicPlaylistTrack.rom_id, MusicPlaylistTrack.md5_hash).where(
                    MusicPlaylistTrack.playlist_id == playlist_id,
                    MusicPlaylistTrack.rom_id.in_({r for r, _ in candidates}),
                )
            )
        }
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
        for rom_id, md5 in new_entries:
            try:
                with session.begin_nested():
                    session.execute(
                        insert(MusicPlaylistTrack).values(
                            playlist_id=playlist_id,
                            rom_id=rom_id,
                            md5_hash=md5,
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
        entries: Sequence[TrackRef],
        session: Session = None,  # type: ignore
    ) -> int:
        if not entries:
            return 0
        result = session.execute(
            delete(MusicPlaylistTrack).where(
                MusicPlaylistTrack.playlist_id == playlist_id,
                or_(
                    *(
                        (MusicPlaylistTrack.rom_id == rom_id)
                        & (MusicPlaylistTrack.md5_hash == md5)
                        for rom_id, md5 in entries
                    )
                ),
            )
        )
        if result.rowcount > 0:
            self._touch(playlist_id, session)
        return result.rowcount

    @begin_session
    def set_playlist_track_order(
        self,
        playlist_id: int,
        ordered_entry_ids: Sequence[int],
        session: Session = None,  # type: ignore
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
        entries: Sequence[TrackRef],
        session: Session = None,  # type: ignore
    ) -> int:
        candidates = list(dict.fromkeys(entries))
        if not candidates:
            return 0
        existing = {
            (rom_id, md5)
            for rom_id, md5 in session.execute(
                select(MusicFavoriteTrack.rom_id, MusicFavoriteTrack.md5_hash).where(
                    MusicFavoriteTrack.user_id == user_id,
                    MusicFavoriteTrack.rom_id.in_({r for r, _ in candidates}),
                )
            )
        }
        new_entries = [e for e in candidates if e not in existing]
        if not new_entries:
            return 0
        added = 0
        for rom_id, md5 in new_entries:
            try:
                with session.begin_nested():
                    session.execute(
                        insert(MusicFavoriteTrack).values(
                            user_id=user_id, rom_id=rom_id, md5_hash=md5
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
        entries: Sequence[TrackRef],
        session: Session = None,  # type: ignore
    ) -> int:
        if not entries:
            return 0
        result = session.execute(
            delete(MusicFavoriteTrack).where(
                MusicFavoriteTrack.user_id == user_id,
                or_(
                    *(
                        (MusicFavoriteTrack.rom_id == rom_id)
                        & (MusicFavoriteTrack.md5_hash == md5)
                        for rom_id, md5 in entries
                    )
                ),
            )
        )
        return result.rowcount

    @staticmethod
    def _touch(playlist_id: int, session: Session) -> None:
        session.execute(
            update(MusicPlaylist)
            .where(MusicPlaylist.id == playlist_id)
            .values(updated_at=datetime.now(timezone.utc))
            .execution_options(synchronize_session="evaluate")
        )
