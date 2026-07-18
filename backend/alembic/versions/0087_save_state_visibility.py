"""Add is_public flag to saves and states for per-user community sharing
(mirrors screenshots/notes visibility).

Revision ID: 0087_save_state_visibility
Revises: 0086_screenshot_visibility
Create Date: 2026-06-20 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0087_save_state_visibility"
down_revision = "0086_screenshot_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("saves", "states"):
        op.add_column(
            table,
            sa.Column(
                "is_public",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            if_not_exists=True,
        )
        op.create_index(f"idx_{table}_public", table, ["is_public"], if_not_exists=True)


def downgrade() -> None:
    for table in ("saves", "states"):
        op.drop_index(f"idx_{table}_public", table_name=table, if_exists=True)
        op.drop_column(table, "is_public", if_exists=True)
