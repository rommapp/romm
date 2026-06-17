"""Speed up gallery search and name ordering on the roms table

This migration adds the database structures the gallery relies on to search
and sort large libraries without full table scans:

- Search indexes on roms.name and roms.fs_name, tailored per backend so the
  search query stays index-backed: a FULLTEXT index on MySQL/MariaDB, and
  pg_trgm GIN indexes on PostgreSQL (installing the pg_trgm extension first).
- A plain idx_roms_name index on roms.name to accelerate name lookups and
  range scans.
- A precomputed, indexed name_sort_key column for natural-sort ordering.
  Sorting by name previously ran a per-row regexp (strip leading articles,
  zero-pad numbers) that no index could cover, forcing a full sort on every
  page. The key is now stored on write and backfilled here, so ordering by
  name — including deep-offset pages — uses idx_roms_name_sort_key.

downgrade() drops every object created here in reverse order, leaving the
pg_trgm extension in place since other objects may depend on it.

Revision ID: 0084
Revises: 0082_save_origin_device
Create Date: 2026-06-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from models.rom import NAME_SORT_KEY_MAX_LENGTH, compute_name_sort_key
from utils.database import is_mariadb, is_mysql, is_postgresql

# revision identifiers, used by Alembic.
revision = "0084"
down_revision = "0082_save_origin_device"
branch_labels = None
depends_on = None

FULLTEXT_INDEX_NAME = "idx_roms_name_fs_name_fulltext"
PG_NAME_INDEX = "idx_roms_name_trgm"
PG_FS_NAME_INDEX = "idx_roms_fs_name_trgm"

_BACKFILL_BATCH = 1000


def upgrade() -> None:
    bind = op.get_bind()

    # 1. DB-specific search indexes on roms.name and roms.fs_name.
    if is_mysql(bind) or is_mariadb(bind):
        op.execute(
            sa.text(
                f"CREATE FULLTEXT INDEX {FULLTEXT_INDEX_NAME} "
                "ON roms (name, fs_name)"
            )
        )
    elif is_postgresql(bind):
        # pg_trgm is a trusted extension since PostgreSQL 13, so a non-superuser
        # with CREATE on the database can install it.
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        op.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS {PG_NAME_INDEX} "
                "ON roms USING gin (name gin_trgm_ops)"
            )
        )
        op.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS {PG_FS_NAME_INDEX} "
                "ON roms USING gin (fs_name gin_trgm_ops)"
            )
        )

    # 2. Plain index on roms.name.
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            "idx_roms_name",
            ["name"],
            unique=False,
            if_not_exists=True,
        )

    # 3. Precomputed name_sort_key column for natural-sort ordering.
    op.add_column(
        "roms",
        sa.Column(
            "name_sort_key",
            sa.String(length=NAME_SORT_KEY_MAX_LENGTH),
            nullable=True,
        ),
    )

    roms = sa.table(
        "roms",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("name_sort_key", sa.String),
    )

    rows = bind.execute(sa.select(roms.c.id, roms.c.name)).fetchall()
    update_stmt = (
        roms.update()
        .where(roms.c.id == sa.bindparam("_id"))
        .values(name_sort_key=sa.bindparam("_key"))
    )
    for start in range(0, len(rows), _BACKFILL_BATCH):
        batch = rows[start : start + _BACKFILL_BATCH]
        bind.execute(
            update_stmt,
            [{"_id": row.id, "_key": compute_name_sort_key(row.name)} for row in batch],
        )

    op.create_index("idx_roms_name_sort_key", "roms", ["name_sort_key"])


def downgrade() -> None:
    bind = op.get_bind()

    # 3. name_sort_key column and its index.
    op.drop_index("idx_roms_name_sort_key", table_name="roms")
    op.drop_column("roms", "name_sort_key")

    # 2. Plain index on roms.name.
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_name", if_exists=True)

    # 1. DB-specific search indexes.
    if is_mysql(bind) or is_mariadb(bind):
        op.execute(sa.text(f"DROP INDEX {FULLTEXT_INDEX_NAME} ON roms"))
    elif is_postgresql(bind):
        # Leave the pg_trgm extension in place; other objects may depend on it.
        op.execute(sa.text(f"DROP INDEX IF EXISTS {PG_FS_NAME_INDEX}"))
        op.execute(sa.text(f"DROP INDEX IF EXISTS {PG_NAME_INDEX}"))
