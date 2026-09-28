"""key soundtrack tracks by song, so a file can hold several

Revision ID: 0145_track_meta_songs
Revises: 0144_user_oidc_sub
Create Date: 2026-09-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import has_column, is_postgresql

# revision identifiers, used by Alembic.
revision = "0145_track_meta_songs"
down_revision = "0144_user_oidc_sub"
branch_labels = None
depends_on = None

_SONG_TABLES = ("track_meta", "music_favorite_tracks", "music_playlist_tracks")
_M3U_FK = "fk_track_meta_m3u_file"
_M3U_INDEX = "ix_track_meta_m3u_file_id"
_PLAYLIST_UNIQUE = "unique_music_playlist_track"


def _song_column() -> sa.Column[int]:
    return sa.Column(
        "song", sa.SmallInteger(), nullable=False, server_default=sa.text("0")
    )


def _replace_primary_key(table: str, columns: tuple[str, ...]) -> None:
    conn = op.get_bind()
    current = sa.inspect(conn).get_pk_constraint(table)
    if tuple(current["constrained_columns"]) == columns:
        return
    listed = ", ".join(columns)
    # One statement, since MariaDB refuses to drop a key a foreign key relies on.
    if is_postgresql(conn):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {current['name']}, "
            f"ADD PRIMARY KEY ({listed})"
        )
    else:
        op.execute(f"ALTER TABLE {table} DROP PRIMARY KEY, ADD PRIMARY KEY ({listed})")


def _playlist_unique_columns(conn: sa.Connection) -> tuple[str, ...] | None:
    inspector = sa.inspect(conn)
    for constraint in inspector.get_unique_constraints("music_playlist_tracks"):
        if constraint["name"] == _PLAYLIST_UNIQUE:
            return tuple(constraint["column_names"])
    # MariaDB and MySQL report a unique constraint as a unique index.
    for index in inspector.get_indexes("music_playlist_tracks"):
        if index["name"] == _PLAYLIST_UNIQUE:
            return tuple(str(column) for column in index["column_names"])
    return None


def _replace_playlist_unique(columns: tuple[str, ...]) -> None:
    conn = op.get_bind()
    current = _playlist_unique_columns(conn)
    if current == columns:
        return
    add = f"ADD CONSTRAINT {_PLAYLIST_UNIQUE} UNIQUE ({', '.join(columns)})"
    if current is None:
        op.execute(f"ALTER TABLE music_playlist_tracks {add}")
        return
    drop = "DROP CONSTRAINT" if is_postgresql(conn) else "DROP INDEX"
    op.execute(f"ALTER TABLE music_playlist_tracks {drop} {_PLAYLIST_UNIQUE}, {add}")


def _has_m3u_foreign_key(conn: sa.Connection) -> bool:
    return any(
        key["name"] == _M3U_FK
        for key in sa.inspect(conn).get_foreign_keys("track_meta")
    )


def upgrade() -> None:
    conn = op.get_bind()
    for table in _SONG_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(_song_column(), if_not_exists=True)

    with op.batch_alter_table("track_meta", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("m3u_file_id", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.create_index(_M3U_INDEX, ["m3u_file_id"], if_not_exists=True)
    if not _has_m3u_foreign_key(conn):
        op.create_foreign_key(
            _M3U_FK,
            "track_meta",
            "rom_files",
            ["m3u_file_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _replace_primary_key("track_meta", ("rom_file_id", "song"))
    _replace_primary_key("music_favorite_tracks", ("user_id", "rom_file_id", "song"))
    _replace_playlist_unique(("playlist_id", "rom_file_id", "song"))


def downgrade() -> None:
    conn = op.get_bind()
    # Only a file's first song survives, as the old schema had one row per file.
    for table in _SONG_TABLES:
        if has_column(conn, table, "song"):
            song = sa.column("song", sa.SmallInteger())
            op.execute(sa.table(table, song).delete().where(song > 0))

    _replace_playlist_unique(("playlist_id", "rom_file_id"))
    _replace_primary_key("music_favorite_tracks", ("user_id", "rom_file_id"))
    _replace_primary_key("track_meta", ("rom_file_id",))

    if _has_m3u_foreign_key(conn):
        op.drop_constraint(_M3U_FK, "track_meta", type_="foreignkey")
    with op.batch_alter_table("track_meta", schema=None) as batch_op:
        batch_op.drop_index(_M3U_INDEX, if_exists=True)
        batch_op.drop_column("m3u_file_id", if_exists=True)

    for table in _SONG_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("song", if_exists=True)
