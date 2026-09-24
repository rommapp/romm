"""Materialize the HowLongToBeat main-story time as a generated column

``hltb_metadata`` is a raw provider blob, so the gallery could show a game's
length on its detail page but could not sort or filter the library by it. This
adds ``generated_hltb_main_story`` (seconds), a STORED generated column the
engine keeps in sync with the blob, plus the index the sort and the range
filter walk. See issue #4232.

The expression lives in `utils.roms_columns`, which adds the column in the
table copy shared by every 5.3.0 revision that widens `roms`. Following 0098,
MariaDB unquotes before the numeric CAST so a STORED INSERT does not trip
strict-mode truncation, and the digits-only gate makes a malformed blob yield
NULL instead of aborting the write.

Revision ID: 0128_hltb_main_story_column
Revises: 0127_rom_identity_keys
Create Date: 2026-09-08 00:00:00.000000

"""

from alembic import op  # type: ignore[attr-defined]

from utils.roms_columns import HLTB_MAIN_STORY_COLUMN, ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0128_hltb_main_story_column"
down_revision = "0127_rom_identity_keys"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_roms_hltb_main_story"


def upgrade() -> None:
    ensure_roms_columns(op.get_bind())
    op.create_index(INDEX_NAME, "roms", [HLTB_MAIN_STORY_COLUMN], if_not_exists=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="roms", if_exists=True)
    op.execute(f"ALTER TABLE roms DROP COLUMN {HLTB_MAIN_STORY_COLUMN}")
