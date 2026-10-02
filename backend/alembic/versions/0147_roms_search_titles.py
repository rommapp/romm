"""Store each ROM's folded name and aliases for search ranking

Revision ID: 0147_roms_search_titles
Revises: 0146_roms_search_aliases
Create Date: 2026-10-01 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from models.rom import ALTERNATIVE_NAME_SOURCES, compute_search_titles
from utils.database import CustomJSON
from utils.roms_columns import SEARCH_TITLES_COLUMN, ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0147_roms_search_titles"
down_revision = "0146_roms_search_aliases"
branch_labels = None
depends_on = None

BATCH_SIZE = 1000

ROMS = sa.table(
    "roms",
    sa.column("id", sa.Integer()),
    sa.column("name", sa.String()),
    sa.column(SEARCH_TITLES_COLUMN, sa.Text()),
    *(sa.column(column, CustomJSON()) for column, _ in ALTERNATIVE_NAME_SOURCES),
)


def _fill_search_titles(conn: sa.Connection) -> None:
    """Fill the rows still without titles, so an interrupted run resumes."""
    # Only each provider's titles are read, not the whole metadata blob.
    titles = [ROMS.c[column][key] for column, key in ALTERNATIVE_NAME_SOURCES]
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


def upgrade() -> None:
    conn = op.get_bind()
    ensure_roms_columns(conn)
    _fill_search_titles(conn)


def downgrade() -> None:
    op.drop_column("roms", SEARCH_TITLES_COLUMN, if_exists=True)
