"""Materialize the HowLongToBeat main-story time as a generated column

``hltb_metadata`` is a raw provider blob, so the gallery could show a game's
length on its detail page but could not sort or filter the library by it. This
adds ``generated_hltb_main_story`` (seconds), a STORED generated column the
engine keeps in sync with the blob, plus the index the sort and the range
filter walk. See issue #4232.

Following 0098: MariaDB unquotes before the numeric CAST so a STORED INSERT
does not trip strict-mode truncation, and the digits-only gate makes a
malformed blob yield NULL instead of aborting the write.

Revision ID: 0128_hltb_main_story_column
Revises: 0127_rom_identity_keys
Create Date: 2026-09-08 00:00:00.000000

"""

from alembic import op  # type: ignore[attr-defined]

from utils.database import has_column, hltb_main_story_sql, is_postgresql

# revision identifiers, used by Alembic.
revision = "0128_hltb_main_story_column"
down_revision = "0127_rom_identity_keys"
branch_labels = None
depends_on = None

COLUMN_NAME = "generated_hltb_main_story"
INDEX_NAME = "idx_roms_hltb_main_story"


def upgrade() -> None:
    connection = op.get_bind()

    # 0123 adds this column in the same ALTER as its own generated columns, so
    # this only fires for a database that stopped between the two revisions.
    if not has_column(connection, "roms", COLUMN_NAME):
        expr = hltb_main_story_sql(is_postgresql(connection))
        op.execute(  # nosec B608
            f"ALTER TABLE roms ADD COLUMN {COLUMN_NAME} BIGINT "
            f"GENERATED ALWAYS AS ({expr}) STORED"
        )

    op.create_index(INDEX_NAME, "roms", [COLUMN_NAME], if_not_exists=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="roms", if_exists=True)
    op.execute(f"ALTER TABLE roms DROP COLUMN {COLUMN_NAME}")
