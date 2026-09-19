"""Make the nullable gallery sorts readable from an index

Sorting the gallery by release date, rating or HowLongToBeat time placed unset
roms last through `ORDER BY <column> IS NULL, <column>`. That leading term is
an expression, so MariaDB and MySQL could not read the order out of
`idx_roms_<column>`: every scroll window scanned `roms` (a dozen JSON provider
blobs per row) and filesorted it. PostgreSQL had the mirror problem
descending, where `DESC NULLS LAST` does not match the index's own order.

Each column now carries a STORED `_unset` flag and an `idx_roms_<column>_sort`
pair the ascending sort leads with, plus an `idx_roms_<column>_desc` on
PostgreSQL for the descending one. The columns and the indexes both come from
`utils.roms_columns`, so they join the table copy every 5.3.0 revision that
widens `roms` shares.

Revision ID: 0129_indexed_gallery_sorts
Revises: 0128_hltb_main_story_column
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
revision = "0129_indexed_gallery_sorts"
down_revision = "0128_hltb_main_story_column"
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
