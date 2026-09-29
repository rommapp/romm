"""Search the gallery by every provider's alternative titles

The providers' alternative titles ("FF9", "Final Fantasy 9") only lived in the
raw metadata blobs, where no search index reaches. This adds
``generated_search_aliases``, a STORED generated column the engine fills from
those blobs, and puts it under the gallery search's index: the FULLTEXT index
is rebuilt over (name, fs_name, aliases) on MariaDB and MySQL, and a pg_trgm
GIN index joins 0084's on PostgreSQL.

The expression lives in `utils.roms_columns`, which adds the column in the
table copy shared by every revision that widens `roms`.

Revision ID: 0145_roms_search_aliases
Revises: 0144_user_oidc_sub
Create Date: 2026-09-29 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import (
    ROMS_SEARCH_ALIASES_TRGM_INDEX,
    ROMS_SEARCH_FULLTEXT_COLUMNS,
    ROMS_SEARCH_FULLTEXT_INDEX,
    SEARCH_ALIASES_COLUMN,
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
NAME_FULLTEXT_COLUMNS = ("name", "fs_name")


def _swap_fulltext_index(
    conn: sa.Connection,
    *,
    drop: str,
    create: str,
    columns: tuple[str, ...],
) -> None:
    # Each step is guarded so a run that died between the two replays cleanly.
    existing = {index["name"] for index in sa.inspect(conn).get_indexes("roms")}
    if drop in existing:
        op.execute(f"ALTER TABLE roms DROP INDEX {drop}")
    if create not in existing:
        op.execute(f"CREATE FULLTEXT INDEX {create} ON roms ({', '.join(columns)})")


def upgrade() -> None:
    conn = op.get_bind()
    ensure_roms_columns(conn)

    if is_postgresql(conn):
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {ROMS_SEARCH_ALIASES_TRGM_INDEX} "
            f"ON roms USING gin ({SEARCH_ALIASES_COLUMN} gin_trgm_ops)"
        )
        return

    _swap_fulltext_index(
        conn,
        drop=NAME_FULLTEXT_INDEX,
        create=ROMS_SEARCH_FULLTEXT_INDEX,
        columns=ROMS_SEARCH_FULLTEXT_COLUMNS,
    )


def downgrade() -> None:
    conn = op.get_bind()

    if is_postgresql(conn):
        op.execute(f"DROP INDEX IF EXISTS {ROMS_SEARCH_ALIASES_TRGM_INDEX}")
    else:
        _swap_fulltext_index(
            conn,
            drop=ROMS_SEARCH_FULLTEXT_INDEX,
            create=NAME_FULLTEXT_INDEX,
            columns=NAME_FULLTEXT_COLUMNS,
        )

    op.drop_column("roms", SEARCH_ALIASES_COLUMN, if_exists=True)
