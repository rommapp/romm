"""Move rom_files.audio_meta JSON into a dedicated track_meta table.

Revision ID: 0094_track_meta_table
Revises: 0093_states_rom_user_index
Create Date: 2026-06-30 00:00:00.000000

"""

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from logger.logger import log
from utils.audio_tags import track_meta_columns
from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0094_track_meta_table"
down_revision = "0093_states_rom_user_index"
branch_labels = None
depends_on = None

_BATCH = 500


def _src_rom_files() -> sa.TableClause:
    # Typed CustomJSON so the driver deserializes it (MariaDB stores JSON as text).
    return sa.table(
        "rom_files",
        sa.column("id", sa.Integer),
        sa.column("rom_id", sa.Integer),
        sa.column("audio_meta", CustomJSON()),
    )


def _track_meta() -> sa.TableClause:
    return sa.table(
        "track_meta",
        sa.column("rom_file_id", sa.Integer),
        sa.column("rom_id", sa.Integer),
        sa.column("title", sa.String),
        sa.column("artist", sa.String),
        sa.column("album", sa.String),
        sa.column("genre", sa.String),
        sa.column("year", sa.SmallInteger),
        sa.column("track", sa.SmallInteger),
        sa.column("disc", sa.SmallInteger),
        sa.column("duration_seconds", sa.Float),
        sa.column("has_embedded_cover", sa.Boolean),
        sa.column("cover_path", sa.String),
    )


def upgrade() -> None:
    conn = op.get_bind()

    # Guarded so a re-run after a partial failure doesn't hit an existing table.
    if "track_meta" not in inspect(conn).get_table_names():
        op.create_table(
            "track_meta",
            sa.Column("rom_file_id", sa.Integer(), nullable=False),
            sa.Column("rom_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=512), nullable=True),
            sa.Column("artist", sa.String(length=512), nullable=True),
            sa.Column("album", sa.String(length=512), nullable=True),
            sa.Column("genre", sa.String(length=255), nullable=True),
            sa.Column("year", sa.SmallInteger(), nullable=True),
            sa.Column("track", sa.SmallInteger(), nullable=True),
            sa.Column("disc", sa.SmallInteger(), nullable=True),
            sa.Column("duration_seconds", sa.Float(), nullable=True),
            sa.Column(
                "has_embedded_cover",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("cover_path", sa.String(length=1024), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["rom_file_id"], ["rom_files.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("rom_file_id"),
        )
        with op.batch_alter_table("track_meta", schema=None) as batch_op:
            batch_op.create_index("idx_track_meta_rom_id", ["rom_id"])
            batch_op.create_index("idx_track_meta_duration", ["duration_seconds"])
            batch_op.create_index("idx_track_meta_year", ["year"])
            batch_op.create_index("idx_track_meta_artist", ["artist"])
            batch_op.create_index("idx_track_meta_album", ["album"])

    # Backfill in batches; clear first so a partial re-run starts clean.
    src, dst = _src_rom_files(), _track_meta()
    conn.execute(sa.delete(dst))
    expected = expected_covers = 0
    result = conn.execute(
        sa.select(src.c.id, src.c.rom_id, src.c.audio_meta).where(
            src.c.audio_meta.isnot(None)
        )
    )
    while True:
        batch = result.fetchmany(_BATCH)
        if not batch:
            break
        values = []
        for row in batch:
            meta = row.audio_meta
            if isinstance(meta, str):
                meta = json.loads(meta)
            cols = track_meta_columns(meta or {})
            if cols["cover_path"] is not None:
                expected_covers += 1
            values.append({"rom_file_id": row.id, "rom_id": row.rom_id, **cols})
        conn.execute(sa.insert(dst), values)
        expected += len(batch)

    # A mismatch rolls the still-uncommitted inserts back, leaving audio_meta intact.
    inserted = conn.execute(sa.select(sa.func.count()).select_from(dst)).scalar_one()
    covers = conn.execute(
        sa.select(sa.func.count()).select_from(dst).where(dst.c.cover_path.isnot(None))
    ).scalar_one()
    if inserted != expected:
        raise RuntimeError(
            f"track_meta backfill row mismatch: {inserted} != {expected}"
        )
    if covers != expected_covers:
        raise RuntimeError(f"track_meta cover mismatch: {covers} != {expected_covers}")
    log.info(f"[0094] migrated {inserted} track_meta rows ({covers} with covers)")

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_column("audio_meta", if_exists=True)


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("audio_meta", CustomJSON(), nullable=True), if_not_exists=True
        )

    src, dst = _track_meta(), _src_rom_files()
    result = conn.execute(
        sa.select(
            src.c.rom_file_id,
            src.c.title,
            src.c.artist,
            src.c.album,
            src.c.genre,
            src.c.year,
            src.c.track,
            src.c.disc,
            src.c.duration_seconds,
            src.c.has_embedded_cover,
            src.c.cover_path,
        )
    )
    while True:
        batch = result.fetchmany(_BATCH)
        if not batch:
            break
        for row in batch:
            meta = {
                "title": row.title,
                "artist": row.artist,
                "album": row.album,
                "genre": row.genre,
                "year": str(row.year) if row.year is not None else None,
                "track": str(row.track) if row.track is not None else None,
                "disc": str(row.disc) if row.disc is not None else None,
                "duration_seconds": row.duration_seconds,
                "has_embedded_cover": row.has_embedded_cover,
                "cover_path": row.cover_path,
            }
            conn.execute(
                sa.update(dst)
                .where(dst.c.id == row.rom_file_id)
                .values(audio_meta=meta)
            )

    op.drop_table("track_meta")
