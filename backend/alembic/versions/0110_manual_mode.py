"""Add manual_mode to install_sessions.

Revision ID: 0110_manual_mode
Revises: 0109_install_auto_mode
Create Date: 2026-09-26 00:00:00.000000

manual_mode: per-install override that forces AWAITING_INSTALLER even when
candidates exist, so the user can pick the installer themselves.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0110_manual_mode"
down_revision = "0109_install_auto_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("install_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "manual_mode",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("install_sessions") as batch_op:
        batch_op.drop_column("manual_mode")