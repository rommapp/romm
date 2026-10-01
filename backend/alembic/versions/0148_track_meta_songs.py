"""give each soundtrack song its own track row, so a file can hold several

Revision ID: 0148_track_meta_songs
Revises: 0147_roms_search_titles
Create Date: 2026-09-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import has_column, is_postgresql

# revision identifiers, used by Alembic.
revision = "0148_track_meta_songs"
down_revision = "0147_roms_search_titles"
branch_labels = None
depends_on = None

_FILE_SONG_UNIQUE = "uq_track_meta_file_song"
_M3U_FK = "fk_track_meta_m3u_file"
_M3U_INDEX = "ix_track_meta_m3u_file_id"
_PLAYLIST_UNIQUE = "unique_music_playlist_track"

# The tables that point at a track, each with the other column in its key.
_REFERENCES = {
    "music_favorite_tracks": "user_id",
    "music_playlist_tracks": "playlist_id",
}


def _pk_columns(conn: sa.Connection, table: str) -> tuple[str, ...]:
    return tuple(sa.inspect(conn).get_pk_constraint(table)["constrained_columns"])


def _fk_name(conn: sa.Connection, table: str, column: str) -> str | None:
    for key in sa.inspect(conn).get_foreign_keys(table):
        if key["constrained_columns"] == [column]:
            return key["name"]
    return None


def _is_nullable(conn: sa.Connection, table: str, column: str) -> bool:
    return any(
        c["name"] == column and c["nullable"]
        for c in sa.inspect(conn).get_columns(table)
    )


def _unique_columns(conn: sa.Connection, table: str, name: str) -> tuple[str, ...]:
    inspector = sa.inspect(conn)
    for constraint in inspector.get_unique_constraints(table):
        if constraint["name"] == name:
            return tuple(constraint["column_names"])
    # MariaDB and MySQL report a unique constraint as a unique index.
    for index in inspector.get_indexes(table):
        if index["name"] == name:
            return tuple(str(column) for column in index["column_names"])
    return ()


def _replace_key(table: str, columns: tuple[str, ...]) -> None:
    """Swap a favorites primary key, or a playlist's unique key."""
    conn = op.get_bind()
    listed = ", ".join(columns)
    # One statement, since MariaDB refuses to drop a key a foreign key relies on.
    if table == "music_playlist_tracks":
        if _unique_columns(conn, table, _PLAYLIST_UNIQUE) == columns:
            return
        drop = "DROP CONSTRAINT" if is_postgresql(conn) else "DROP INDEX"
        op.execute(
            f"ALTER TABLE {table} {drop} {_PLAYLIST_UNIQUE}, "
            f"ADD CONSTRAINT {_PLAYLIST_UNIQUE} UNIQUE ({listed})"
        )
        return
    if _pk_columns(conn, table) == columns:
        return
    if is_postgresql(conn):
        name = sa.inspect(conn).get_pk_constraint(table)["name"]
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT {name}, ADD PRIMARY KEY ({listed})"
        )
    else:
        op.execute(f"ALTER TABLE {table} DROP PRIMARY KEY, ADD PRIMARY KEY ({listed})")


def _backfill(table: str, target: str, source: str) -> None:
    """Fill `target` through each row's first song, dropping rows that have none."""
    ref = sa.table(table, sa.column(target), sa.column(source))
    track = sa.table(
        "track_meta", sa.column("id"), sa.column("rom_file_id"), sa.column("song")
    )
    by_name = {"track_id": track.c.id, "rom_file_id": track.c.rom_file_id}
    op.execute(
        ref.update()
        .where(ref.c[target].is_(None))
        .values(
            {
                target: sa.select(by_name[target])
                .where(by_name[source] == ref.c[source], track.c.song == 0)
                .scalar_subquery()
            }
        )
    )
    op.execute(ref.delete().where(ref.c[target].is_(None)))


def _repoint(table: str, lead: str, old: str, new: str) -> None:
    """Move a reference table's key from its `old` column to `new`."""
    conn = op.get_bind()
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(new, sa.Integer(), nullable=True), if_not_exists=True
        )
    if has_column(conn, table, old):
        _backfill(table, new, old)
    if _is_nullable(conn, table, new):
        op.alter_column(table, new, existing_type=sa.Integer(), nullable=False)

    old_fk = _fk_name(conn, table, old)
    if old_fk:
        op.drop_constraint(old_fk, table, type_="foreignkey")
    _replace_key(table, (lead, new))
    with op.batch_alter_table(table, schema=None) as batch_op:
        if old == "track_id":
            batch_op.drop_index(f"ix_{table}_track_id", if_exists=True)
        batch_op.drop_column(old, if_exists=True)

    if new == "track_id":
        op.create_index(f"ix_{table}_track_id", table, ["track_id"], if_not_exists=True)
        target, name = "track_meta", f"fk_{table}_track"
    else:
        # 0124 indexed these foreign keys on PostgreSQL only.
        if is_postgresql(conn):
            op.create_index(
                f"ix_{table}_rom_file_id", table, ["rom_file_id"], if_not_exists=True
            )
        target, name = "rom_files", f"fk_{table}_rom_file"
    if not _fk_name(conn, table, new):
        op.create_foreign_key(name, table, target, [new], ["id"], ondelete="CASCADE")


def _give_tracks_ids() -> None:
    conn = op.get_bind()
    if has_column(conn, "track_meta", "id"):
        return
    unique = f"ADD CONSTRAINT {_FILE_SONG_UNIQUE} UNIQUE (rom_file_id, song)"
    if is_postgresql(conn):
        name = sa.inspect(conn).get_pk_constraint("track_meta")["name"]
        op.execute(
            f"ALTER TABLE track_meta DROP CONSTRAINT {name}, "
            f"ADD COLUMN id SERIAL PRIMARY KEY, {unique}"
        )
    else:
        op.execute(
            "ALTER TABLE track_meta DROP PRIMARY KEY, "
            f"ADD COLUMN id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY, {unique}"
        )


def _drop_track_ids() -> None:
    conn = op.get_bind()
    if not has_column(conn, "track_meta", "id"):
        return
    if is_postgresql(conn):
        name = sa.inspect(conn).get_pk_constraint("track_meta")["name"]
        op.execute(
            f"ALTER TABLE track_meta DROP CONSTRAINT {_FILE_SONG_UNIQUE}, "
            f"DROP CONSTRAINT {name}, DROP COLUMN id, ADD PRIMARY KEY (rom_file_id)"
        )
    else:
        op.execute(
            f"ALTER TABLE track_meta DROP INDEX {_FILE_SONG_UNIQUE}, "
            "DROP PRIMARY KEY, DROP COLUMN id, ADD PRIMARY KEY (rom_file_id)"
        )


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("track_meta", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "song", sa.SmallInteger(), nullable=False, server_default=sa.text("0")
            ),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("m3u_file_id", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.create_index(_M3U_INDEX, ["m3u_file_id"], if_not_exists=True)
    if not _fk_name(conn, "track_meta", "m3u_file_id"):
        op.create_foreign_key(
            _M3U_FK,
            "track_meta",
            "rom_files",
            ["m3u_file_id"],
            ["id"],
            ondelete="SET NULL",
        )
    _give_tracks_ids()

    for table, lead in _REFERENCES.items():
        _repoint(table, lead, old="rom_file_id", new="track_id")


def downgrade() -> None:
    conn = op.get_bind()
    # Only a file's first song survives, as the old schema had one row per file.
    for table, lead in _REFERENCES.items():
        _repoint(table, lead, old="track_id", new="rom_file_id")
    if has_column(conn, "track_meta", "song"):
        song = sa.column("song", sa.SmallInteger())
        op.execute(sa.table("track_meta", song).delete().where(song > 0))
    _drop_track_ids()

    m3u_fk = _fk_name(conn, "track_meta", "m3u_file_id")
    if m3u_fk:
        op.drop_constraint(m3u_fk, "track_meta", type_="foreignkey")
    with op.batch_alter_table("track_meta", schema=None) as batch_op:
        batch_op.drop_index(_M3U_INDEX, if_exists=True)
        batch_op.drop_column("m3u_file_id", if_exists=True)
        batch_op.drop_column("song", if_exists=True)
