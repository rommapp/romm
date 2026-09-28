"""key soundtrack tracks by song, so a file can hold several

Revision ID: 0144_track_meta_songs
Revises: 0143_sibling_platform_names
Create Date: 2026-09-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0144_track_meta_songs"
down_revision = "0143_sibling_platform_names"
branch_labels = None
depends_on = None

_SONG_TABLES = ("track_meta", "music_favorite_tracks", "music_playlist_tracks")


def _song_column() -> sa.Column:
    return sa.Column(
        "song", sa.SmallInteger(), nullable=False, server_default=sa.text("0")
    )


def _replace_primary_key(table: str, columns: str) -> None:
    # One statement, since MariaDB refuses to drop a key a foreign key relies on.
    conn = op.get_bind()
    if is_postgresql(conn):
        name = sa.inspect(conn).get_pk_constraint(table)["name"]
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {name}, ADD PRIMARY KEY ({columns})"
        )
    else:
        op.execute(f"ALTER TABLE {table} DROP PRIMARY KEY, ADD PRIMARY KEY ({columns})")


def _replace_playlist_unique(columns: str) -> None:
    name = "unique_music_playlist_track"
    drop = "DROP CONSTRAINT" if is_postgresql(op.get_bind()) else "DROP INDEX"
    op.execute(
        f"ALTER TABLE music_playlist_tracks {drop} {name}, "
        f"ADD CONSTRAINT {name} UNIQUE ({columns})"
    )


def upgrade() -> None:
    for table in _SONG_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(_song_column())

    with op.batch_alter_table("track_meta", schema=None) as batch_op:
        batch_op.add_column(sa.Column("m3u_file_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_track_meta_m3u_file_id", ["m3u_file_id"])
        batch_op.create_foreign_key(
            "fk_track_meta_m3u_file",
            "rom_files",
            ["m3u_file_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _replace_primary_key("track_meta", "rom_file_id, song")
    _replace_primary_key("music_favorite_tracks", "user_id, rom_file_id, song")
    _replace_playlist_unique("playlist_id, rom_file_id, song")


def downgrade() -> None:
    # Only a file's first song survives, as the old schema had one row per file.
    for table in _SONG_TABLES:
        song = sa.column("song")
        op.execute(sa.table(table, song).delete().where(song > 0))

    _replace_playlist_unique("playlist_id, rom_file_id")
    _replace_primary_key("music_favorite_tracks", "user_id, rom_file_id")
    _replace_primary_key("track_meta", "rom_file_id")

    with op.batch_alter_table("track_meta", schema=None) as batch_op:
        batch_op.drop_constraint("fk_track_meta_m3u_file", type_="foreignkey")
        batch_op.drop_index("ix_track_meta_m3u_file_id")
        batch_op.drop_column("m3u_file_id")

    for table in _SONG_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("song")
