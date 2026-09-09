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

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0128_hltb_main_story_column"
down_revision = "0127_rom_identity_keys"
branch_labels = None
depends_on = None

COLUMN_NAME = "generated_hltb_main_story"
INDEX_NAME = "idx_roms_hltb_main_story"

_MARIA_VALUE = "CAST(JSON_UNQUOTE(JSON_EXTRACT(hltb_metadata, '$.main_story')) AS CHAR)"
_MARIA_EXPR = (
    "CASE WHEN JSON_CONTAINS_PATH(hltb_metadata, 'one', '$.main_story') "
    f"AND {_MARIA_VALUE} NOT IN ('null', 'None', '0', '0.0') "
    f"AND {_MARIA_VALUE} REGEXP '^[0-9]+$' "
    f"THEN CAST({_MARIA_VALUE} AS SIGNED) ELSE NULL END"
)

_POSTGRES_VALUE = "hltb_metadata ->> 'main_story'"
_POSTGRES_EXPR = (
    "CASE WHEN hltb_metadata IS NOT NULL AND hltb_metadata ? 'main_story' "
    f"AND ({_POSTGRES_VALUE}) NOT IN ('null', 'None', '0', '0.0') "
    f"AND ({_POSTGRES_VALUE}) ~ '^[0-9]+$' "
    f"THEN ({_POSTGRES_VALUE})::bigint ELSE NULL END"
)


def upgrade() -> None:
    expr = _POSTGRES_EXPR if is_postgresql(op.get_bind()) else _MARIA_EXPR
    op.execute(  # nosec B608
        f"ALTER TABLE roms ADD COLUMN {COLUMN_NAME} BIGINT "
        f"GENERATED ALWAYS AS ({expr}) STORED"
    )
    op.create_index(INDEX_NAME, "roms", [COLUMN_NAME], if_not_exists=True)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="roms", if_exists=True)
    op.execute(f"ALTER TABLE roms DROP COLUMN {COLUMN_NAME}")
