"""Add precomputed name_sort_key column for natural-sort ordering

Ordering the gallery by name previously applied a per-row regexp (strip
articles, zero-pad numbers) that can't use an index, forcing a full sort. This
stores that key in an indexed column so name sorting — including deep-offset
pages — uses idx_roms_name_sort_key instead.

Revision ID: 0085_add_roms_name_sort_key
Revises: 0084_add_roms_name_index
Create Date: 2026-06-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from models.rom import NAME_SORT_KEY_MAX_LENGTH, compute_name_sort_key

# revision identifiers, used by Alembic.
revision = "0085_add_roms_name_sort_key"
down_revision = "0084_add_roms_name_index"
branch_labels = None
depends_on = None

_BACKFILL_BATCH = 1000


def upgrade() -> None:
    op.add_column(
        "roms",
        sa.Column(
            "name_sort_key",
            sa.String(length=NAME_SORT_KEY_MAX_LENGTH),
            nullable=True,
        ),
    )

    bind = op.get_bind()
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
            [
                {"_id": row.id, "_key": compute_name_sort_key(row.name)}
                for row in batch
            ],
        )

    op.create_index("idx_roms_name_sort_key", "roms", ["name_sort_key"])


def downgrade() -> None:
    op.drop_index("idx_roms_name_sort_key", table_name="roms")
    op.drop_column("roms", "name_sort_key")
