"""Add is_favorite and labels to saves and states

A filename and a timestamp cannot tell apart a 100% run from a speedrun seed,
so saves and states carry an owner-only favorite flag and a set of free-text
labels. Neither is indexed: both are only ever read inside an already-narrow
(rom, user) scope. See issue #942.

Revision ID: 0129_save_state_favorites_labels
Revises: 0128_hltb_main_story_column
Create Date: 2026-09-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0129_save_state_favorites_labels"
down_revision = "0128_hltb_main_story_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("saves", "states"):
        op.add_column(
            table,
            sa.Column(
                "is_favorite",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            if_not_exists=True,
        )
        op.add_column(
            table,
            sa.Column("labels", CustomJSON(), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    for table in ("saves", "states"):
        op.drop_column(table, "labels", if_exists=True)
        op.drop_column(table, "is_favorite", if_exists=True)
