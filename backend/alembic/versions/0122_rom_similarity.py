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


def upgrade() -> None:
    op.create_table(
        "rom_similarity",
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
        # Reads are always "top N neighbours of this ROM", so the score rides
        # along in the index to keep the ordering off a filesort.
        sa.Index("idx_rom_similarity_rom_score", "rom_id", "score"),
        # Backs the cascade: without it Postgres seq-scans this table on every
        # ROM delete. Declared inline rather than via a following create_index
        # so InnoDB adopts it for the foreign key instead of silently adding a
        # second index on the same column.
        sa.Index("idx_rom_similarity_related_rom_id", "related_rom_id"),
    )


def downgrade() -> None:
    # Dropping the table takes its indexes and constraints with it. Dropping
    # the indexes first fails on MariaDB, which needs them for the foreign keys.
    op.drop_table("rom_similarity")
