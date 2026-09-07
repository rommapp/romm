"""Add description to platforms so custom platforms can carry context
beyond their name (mirrors collections.description).

Revision ID: 0099_platform_description
Revises: 0098_generated_metadata_columns
Create Date: 2026-07-20 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0099_platform_description"
down_revision = "0098_generated_metadata_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platforms",
        sa.Column("description", sa.Text(), nullable=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("platforms", "description", if_exists=True)
