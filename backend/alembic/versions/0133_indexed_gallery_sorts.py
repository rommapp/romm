"""Make the nullable gallery sorts readable from an index

Placing unset roms last through `ORDER BY <column> IS NULL, <column>` leads
with an expression, which no index serves. Each column now carries a STORED
`_unset` flag and an `idx_roms_<column>_sort` the ascending sort leads with
instead, plus an `idx_roms_<column>_desc` on PostgreSQL, whose descending order
needs spelling out. Both come from `utils.roms_columns`, so they join the table
copy every 5.3.0 revision that widens `roms` shares.

Revision ID: 0133_indexed_gallery_sorts
Revises: 0132_audit_events
Create Date: 2026-09-19 00:00:00.000000

"""

from alembic import op  # type: ignore[attr-defined]

from utils.database import (
    SORTABLE_NULLABLE_ROM_COLUMNS,
    column_names,
    rom_desc_index_name,
    rom_sort_index_name,
    rom_unset_flag_column,
)
from utils.roms_columns import ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0133_indexed_gallery_sorts"
down_revision = "0132_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Adds the flags and creates every index they need, on both dialects.
    ensure_roms_columns(op.get_bind())


def downgrade() -> None:
    conn = op.get_bind()
    present = column_names(conn, "roms")
    for column in SORTABLE_NULLABLE_ROM_COLUMNS:
        op.drop_index(rom_desc_index_name(column), table_name="roms", if_exists=True)
        op.drop_index(rom_sort_index_name(column), table_name="roms", if_exists=True)
        # MySQL has no `DROP COLUMN IF EXISTS`, so a replay is guarded here.
        flag = rom_unset_flag_column(column)
        if flag in present:
            op.execute(f"ALTER TABLE roms DROP COLUMN {flag}")
