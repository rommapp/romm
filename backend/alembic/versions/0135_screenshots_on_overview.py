"""Add a per-screenshot overview visibility flag.

Revision ID: 0135_screenshots_on_overview
Revises: 0134_gallery_sort_indexes
Create Date: 2026-09-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0135_screenshots_on_overview"
down_revision = "0134_gallery_sort_indexes"
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
