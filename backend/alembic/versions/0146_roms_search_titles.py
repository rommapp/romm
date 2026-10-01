"""Search and rank on each ROM's folded name and aliases

Revision ID: 0146_roms_search_titles
Revises: 0145_drop_derivable_columns
Create Date: 2026-09-29 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from models.rom import compute_search_titles
from utils.database import (
    ROMS_SEARCH_FULLTEXT_INDEX,
    ROMS_SEARCH_TITLES_TRGM_INDEX,
    SEARCH_TITLES_COLUMN,
    CustomJSON,
    column_names,
    is_postgresql,
)
from utils.roms_columns import ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0146_roms_search_titles"
down_revision = "0145_drop_derivable_columns"
branch_labels = None
depends_on = None

# 0084's FULLTEXT index, over the name columns alone.
NAME_FULLTEXT_INDEX = "idx_roms_name_fs_name_fulltext"

# (column, key) of each provider's titles, a frozen snapshot of
# `ALTERNATIVE_NAME_SOURCES` so a later provider can't change this revision.
ALIAS_SOURCES = (
    ("igdb_metadata", "alternative_names"),
    ("moby_metadata", "alternate_titles"),
    ("ss_metadata", "alternative_names"),
)

BATCH_SIZE = 1000

ROMS = sa.table(
    "roms",
    sa.column("id", sa.Integer()),
    sa.column("name", sa.String()),
    sa.column(SEARCH_TITLES_COLUMN, sa.Text()),
    *(sa.column(column, CustomJSON()) for column, _ in ALIAS_SOURCES),
)


def _index_names(conn: sa.Connection) -> set[str | None]:
    return {index["name"] for index in sa.inspect(conn).get_indexes("roms")}


def _drop_search_indexes(conn: sa.Connection) -> None:
    if is_postgresql(conn):
        op.execute(f"DROP INDEX IF EXISTS {ROMS_SEARCH_TITLES_TRGM_INDEX}")
        return
    existing = _index_names(conn)
    for index in (NAME_FULLTEXT_INDEX, ROMS_SEARCH_FULLTEXT_INDEX):
        if index in existing:
            op.execute(f"ALTER TABLE roms DROP INDEX {index}")


def _fill_search_titles(conn: sa.Connection) -> None:
    """Fill the rows still without titles, so an interrupted run resumes."""
    # Only each provider's titles are read, not the whole metadata blob.
    titles = [ROMS.c[column][key] for column, key in ALIAS_SOURCES]
    last_id = 0
    while rows := conn.execute(
        sa.select(ROMS.c.id, ROMS.c.name, *titles)
        .where(ROMS.c[SEARCH_TITLES_COLUMN].is_(None), ROMS.c.id > last_id)
        .order_by(ROMS.c.id)
        .limit(BATCH_SIZE)
    ).all():
        filled = {
            rom_id: compute_search_titles(
                name,
                {
                    column: {key: names}
                    for (column, key), names in zip(
                        ALIAS_SOURCES, provider_titles, strict=True
                    )
                },
            )
            for rom_id, name, *provider_titles in rows
        }
        # One statement per batch, since a round trip per row dominates.
        conn.execute(
            sa.update(ROMS)
            .where(ROMS.c.id.in_(filled))
            .values({SEARCH_TITLES_COLUMN: sa.case(filled, value=ROMS.c.id)})
        )
        last_id = rows[-1][0]


def upgrade() -> None:
    conn = op.get_bind()
    # With no FULLTEXT index on the table, the column is added in place and the
    # fill updates no index; the search index is then built over filled rows.
    _drop_search_indexes(conn)
    if SEARCH_TITLES_COLUMN not in column_names(conn, "roms"):
        op.add_column("roms", sa.Column(SEARCH_TITLES_COLUMN, sa.Text()))
    _fill_search_titles(conn)
    ensure_roms_columns(conn)


def downgrade() -> None:
    conn = op.get_bind()

    if is_postgresql(conn):
        op.execute(f"DROP INDEX IF EXISTS {ROMS_SEARCH_TITLES_TRGM_INDEX}")
    else:
        existing = _index_names(conn)
        if NAME_FULLTEXT_INDEX not in existing:
            op.execute(
                f"CREATE FULLTEXT INDEX {NAME_FULLTEXT_INDEX} ON roms (name, fs_name)"
            )
        if ROMS_SEARCH_FULLTEXT_INDEX in existing:
            op.execute(f"ALTER TABLE roms DROP INDEX {ROMS_SEARCH_FULLTEXT_INDEX}")

    # MySQL has no DROP COLUMN IF EXISTS.
    if SEARCH_TITLES_COLUMN in column_names(conn, "roms"):
        op.drop_column("roms", SEARCH_TITLES_COLUMN)
