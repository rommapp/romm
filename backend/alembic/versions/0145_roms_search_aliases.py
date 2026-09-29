"""Search the gallery by every provider's alternative titles

The providers' alternative titles ("FF9", "Final Fantasy 9") only lived in the
raw metadata blobs, where no search index reaches. This adds
``generated_search_aliases``, a STORED generated column the engine fills from
those blobs, and puts it under the gallery search's index: the FULLTEXT index
is rebuilt over (name, fs_name, aliases) on MariaDB and MySQL, and a pg_trgm
GIN index joins 0084's on PostgreSQL.

The expression and both indexes live in `utils.roms_columns`, which adds the
column in the table copy shared by every revision that widens `roms` and puts
the indexes back after any later rebuild.

Revision ID: 0145_roms_search_aliases
Revises: 0144_user_oidc_sub
Create Date: 2026-09-29 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import (
    ROMS_SEARCH_ALIASES_TRGM_INDEX,
    ROMS_SEARCH_FULLTEXT_INDEX,
    SEARCH_ALIASES_COLUMN,
    has_column,
    is_postgresql,
)
from utils.roms_columns import ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0145_roms_search_aliases"
down_revision = "0144_user_oidc_sub"
branch_labels = None
depends_on = None

# 0084's FULLTEXT index, over the name columns alone.
NAME_FULLTEXT_INDEX = "idx_roms_name_fs_name_fulltext"


def _index_names(conn: sa.Connection) -> set[str | None]:
    return {index["name"] for index in sa.inspect(conn).get_indexes("roms")}


def upgrade() -> None:
    conn = op.get_bind()
    # Builds the search index beside 0084's, which goes only after: dropping the
    # last FULLTEXT index first would make InnoDB rebuild the table once more.
    ensure_roms_columns(conn)

    if not is_postgresql(conn) and NAME_FULLTEXT_INDEX in _index_names(conn):
        op.execute(f"ALTER TABLE roms DROP INDEX {NAME_FULLTEXT_INDEX}")


def downgrade() -> None:
    conn = op.get_bind()

    if is_postgresql(conn):
        op.execute(f"DROP INDEX IF EXISTS {ROMS_SEARCH_ALIASES_TRGM_INDEX}")
    else:
        existing = _index_names(conn)
        if NAME_FULLTEXT_INDEX not in existing:
            op.execute(
                f"CREATE FULLTEXT INDEX {NAME_FULLTEXT_INDEX} ON roms (name, fs_name)"
            )
        if ROMS_SEARCH_FULLTEXT_INDEX in existing:
            op.execute(f"ALTER TABLE roms DROP INDEX {ROMS_SEARCH_FULLTEXT_INDEX}")

    # MySQL has no DROP COLUMN IF EXISTS.
    if has_column(conn, "roms", SEARCH_ALIASES_COLUMN):
        op.execute(f"ALTER TABLE roms DROP COLUMN {SEARCH_ALIASES_COLUMN}")
