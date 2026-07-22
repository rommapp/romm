from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import BaseModel

if TYPE_CHECKING:
    from models.user import User

# Playlist and favorite entries reference tracks by (rom_id, md5_hash) instead of
# rom_file_id: rescans purge and re-insert rom_files rows, so file ids churn while
# rom ids and file content hashes are stable.
TRACK_HASH_MAX_LENGTH = 100


class MusicPlaylist(BaseModel):
    __tablename__ = "music_playlists"

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="unique_music_playlist_user_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(length=400))
    description: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(default=False)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    user: Mapped["User"] = relationship(lazy="joined", back_populates="music_playlists")

    @property
    def owner_username(self) -> str:
        return self.user.username

    def __repr__(self) -> str:
        return self.name


class MusicPlaylistTrack(BaseModel):
    __tablename__ = "music_playlist_tracks"

    __table_args__ = (
        UniqueConstraint(
            "playlist_id", "rom_id", "md5_hash", name="unique_music_playlist_track"
        ),
        Index("idx_music_playlist_tracks_playlist_position", "playlist_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("music_playlists.id", ondelete="CASCADE")
    )
    rom_id: Mapped[int] = mapped_column(ForeignKey("roms.id", ondelete="CASCADE"))
    md5_hash: Mapped[str] = mapped_column(String(length=TRACK_HASH_MAX_LENGTH))
    position: Mapped[int] = mapped_column(Integer())


class MusicFavoriteTrack(BaseModel):
    __tablename__ = "music_favorite_tracks"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    rom_id: Mapped[int] = mapped_column(
        ForeignKey("roms.id", ondelete="CASCADE"), primary_key=True
    )
    md5_hash: Mapped[str] = mapped_column(
        String(length=TRACK_HASH_MAX_LENGTH), primary_key=True
    )
