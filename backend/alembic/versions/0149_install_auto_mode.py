"""Add auto_mode, auto_status and auto_detail to install_sessions.

Revision ID: 0109_install_auto_mode
Revises: 0108_install_source_phase
Create Date: 2026-09-25 00:00:00.000000

auto_mode: experimental OCR-driven clicking through the installer's dialogs.
auto_status/auto_detail: what it is doing ("running" / "needs_manual") and
its last action, shown in the Install page widget.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0149_install_auto_mode"
down_revision = "0148_install_source_phase"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("install_sessions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "auto_mode",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("auto_status", sa.String(length=32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("auto_detail", sa.String(length=1000), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("install_sessions") as batch_op:
        batch_op.drop_column("auto_detail")
        batch_op.drop_column("auto_status")
        batch_op.drop_column("auto_mode")
