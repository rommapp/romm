"""Add a per-screenshot overview visibility flag.

Revision ID: 0129_screenshots_on_overview
Revises: 0128_hltb_main_story_column
Create Date: 2026-09-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0129_screenshots_on_overview"
down_revision = "0128_hltb_main_story_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "screenshots",
        sa.Column(
            "is_overview",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("screenshots", "is_overview", if_exists=True)
