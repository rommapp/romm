"""Search and rank on each ROM's folded name and aliases

Revision ID: 0147_roms_search_titles
Revises: 0146_roms_search_aliases
Create Date: 2026-10-01 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from models.rom import (
    ALTERNATIVE_NAME_SOURCES,
    SEARCH_TEXT_MAX_LENGTH,
    compute_search_titles,
)
from utils.database import (
    ROMS_SEARCH_FULLTEXT_INDEX,
    SEARCH_TITLES_COLUMN,
    CustomJSON,
    column_names,
    is_postgresql,
)
from utils.roms_columns import (
    ROMS_METADATA_VIEW_COLUMNS,
    GeneratedColumn,
    ensure_roms_columns,
    rebuild_generated_columns,
)

# revision identifiers, used by Alembic.
revision = "0147_roms_search_titles"
down_revision = "0146_roms_search_aliases"
branch_labels = None
depends_on = None

# 0146's alias column and its index, which `search_titles` replaces.
SEARCH_ALIASES_COLUMN = "generated_search_aliases"
SEARCH_ALIASES_TRGM_INDEX = "idx_roms_search_aliases_trgm"

BATCH_SIZE = 1000

ROMS = sa.table(
    "roms",
    sa.column("id", sa.Integer()),
    sa.column("name", sa.String()),
    sa.column(SEARCH_TITLES_COLUMN, sa.Text()),
    *(sa.column(column, CustomJSON()) for column, _ in ALTERNATIVE_NAME_SOURCES),
)


def _fill_search_titles(conn: sa.Connection) -> bool:
    """Fill the rows still without titles, so an interrupted run resumes.

    Returns:
        Whether any row was filled.
    """
    # Only each provider's titles are read, not the whole metadata blob.
    titles = [ROMS.c[column][key] for column, key in ALTERNATIVE_NAME_SOURCES]
    last_id = 0
    filled_any = False
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
                        ALTERNATIVE_NAME_SOURCES, provider_titles, strict=True
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
        filled_any = True
    return filled_any


def _titles_text(json_array_text: str) -> str:
    """A JSON array of strings as its titles separated by spaces."""
    separator, opening, closing = '", "', '["', '"]'
    return (
        f"REPLACE(REPLACE(REPLACE({json_array_text}, '{separator}', ' '), "
        f"'{opening}', ''), '{closing}', '')"
    )


def _search_aliases_column(pg: bool) -> GeneratedColumn:
    """0146's alias column, as that revision defined it."""
    if pg:
        # concat_ws is only STABLE, which a generated column refuses.
        arrays = [
            f"COALESCE(CASE WHEN jsonb_typeof({src} -> '{key}') = 'array' "
            f"THEN {_titles_text(f"NULLIF({src} -> '{key}', '[]'::jsonb)::text")} || ' ' END, '')"
            for src, key in ALTERNATIVE_NAME_SOURCES
        ]
        expression = "NULLIF(rtrim(" + " || ".join(arrays) + "), '')"
    else:
        values = [
            f"JSON_EXTRACT({src}, '$.{key}')" for src, key in ALTERNATIVE_NAME_SOURCES
        ]
        arrays = [
            f"CASE WHEN CAST(JSON_TYPE({value}) AS CHAR) = 'ARRAY' "
            f"THEN NULLIF({_titles_text(f'CAST({value} AS CHAR)')}, '[]') END"
            for value in values
        ]
        joined = "CONCAT_WS(' ', " + ", ".join(arrays) + ")"
        expression = f"NULLIF(LEFT({joined}, {SEARCH_TEXT_MAX_LENGTH}), '')"
    return GeneratedColumn(SEARCH_ALIASES_COLUMN, "TEXT", expression)


def upgrade() -> None:
    conn = op.get_bind()
    # Moves the search index onto `search_titles` before the old column goes.
    ensure_roms_columns(conn)
    if is_postgresql(conn):
        op.execute(f"DROP INDEX IF EXISTS {SEARCH_ALIASES_TRGM_INDEX}")
    # MySQL has no DROP COLUMN IF EXISTS.
    if SEARCH_ALIASES_COLUMN in column_names(conn, "roms"):
        op.execute(f"ALTER TABLE roms DROP COLUMN {SEARCH_ALIASES_COLUMN}")
    # Growing every row in place leaves InnoDB's pages split, which nothing
    # compacts later; one rebuild keeps the search as fast as before.
    if _fill_search_titles(conn) and not is_postgresql(conn):
        op.execute("ALTER TABLE roms FORCE")


def downgrade() -> None:
    conn = op.get_bind()
    pg = is_postgresql(conn)
    present = column_names(conn, "roms")
    if SEARCH_TITLES_COLUMN in present or SEARCH_ALIASES_COLUMN not in present:
        rebuild_generated_columns(
            conn,
            add=(
                [] if SEARCH_ALIASES_COLUMN in present else [_search_aliases_column(pg)]
            ),
            drop=[SEARCH_TITLES_COLUMN],
            view_columns=ROMS_METADATA_VIEW_COLUMNS,
        )

    existing = {index["name"] for index in sa.inspect(conn).get_indexes("roms")}
    if pg and SEARCH_ALIASES_TRGM_INDEX not in existing:
        op.execute(
            f"CREATE INDEX {SEARCH_ALIASES_TRGM_INDEX} ON roms "
            f"USING gin ({SEARCH_ALIASES_COLUMN} gin_trgm_ops)"
        )
    elif not pg and ROMS_SEARCH_FULLTEXT_INDEX not in existing:
        op.execute(
            f"CREATE FULLTEXT INDEX {ROMS_SEARCH_FULLTEXT_INDEX} ON roms "
            f"(name, fs_name, {SEARCH_ALIASES_COLUMN})"
        )
