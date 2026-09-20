"""Precomputed item-item similarity edges for the recommendations engine

Recommendations previously came straight from IGDB's ``similar_games``, which
knows nothing about which of those games are actually in the library and is
absent entirely for anything IGDB never matched. ``rom_similarity`` holds a
library-relative similarity graph built from the normalised metadata, the IGDB
prior, collection co-membership and co-play, so both the "Similar games"
section and the personalised feed read a single indexed table.

The table is rewritten wholesale by the recommendations task rather than
maintained incrementally, because the IDF weighting that makes the scores
library-relative shifts as the library grows. Rows are bounded at roughly
``rom_count * MAX_NEIGHBOURS``.

Revision ID: 0122_rom_similarity
Revises: 0121_state_disc_file
Create Date: 2026-08-07 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0122_rom_similarity"
down_revision = "0121_state_disc_file"
branch_labels = None
depends_on = None


TABLE = "rom_similarity"

# (name, columns), named here so a replay can fill in whichever is missing.
INDEXES = (
    # Reads are always "top N neighbours of this ROM", so the score rides along
    # in the index to keep the ordering off a filesort.
    ("idx_rom_similarity_rom_score", ["rom_id", "score"]),
    # Backs the cascade: Postgres seq-scans this table on every ROM delete
    # without it, and InnoDB re-points the foreign key at it.
    ("idx_rom_similarity_related_rom_id", ["related_rom_id"]),
)


def upgrade() -> None:
    # Alembic issues table-level indexes as their own statements after the
    # CREATE TABLE, so a run can die between them; each is guarded separately.
    op.create_table(
        TABLE,
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("related_rom_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reasons", CustomJSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rom_id", "related_rom_id"),
        if_not_exists=True,
    )

    for name, columns in INDEXES:
        op.create_index(name, TABLE, columns, unique=False, if_not_exists=True)


def downgrade() -> None:
    # Dropping the table takes its indexes and constraints with it. Dropping
    # the indexes first fails on MariaDB, which needs them for the foreign keys.
    op.drop_table(TABLE, if_exists=True)
