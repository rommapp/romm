"""Add auto_mode, auto_status and auto_detail to install_sessions.

Revision ID: 0149_install_auto_mode
Revises: 0148_install_source_phase
Create Date: 2026-09-25 00:00:00.000000

auto_mode: experimental OCR-driven clicking through the installer's dialogs.
auto_status/auto_detail: what it is doing ("running" / "needs_manual") and
its last action, shown in the Install page widget.
"""

import sqlalchemy as sa
from alembic import op

from utils.database import has_column

# revision identifiers, used by Alembic.
revision = "0149_install_auto_mode"
down_revision = "0148_install_source_phase"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("install_sessions") as batch_op:
        # Guarded individually: a MariaDB/MySQL crash between two of these
        # ADD COLUMNs (each auto-commits on its own) would otherwise replay
        # the whole revision and fail re-adding the one that already landed.
        if not has_column(conn, "install_sessions", "auto_mode"):
            batch_op.add_column(
                sa.Column(
                    "auto_mode",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if not has_column(conn, "install_sessions", "auto_status"):
            batch_op.add_column(
                sa.Column("auto_status", sa.String(length=32), nullable=True)
            )
        if not has_column(conn, "install_sessions", "auto_detail"):
            batch_op.add_column(
                sa.Column("auto_detail", sa.String(length=1000), nullable=True)
            )


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("install_sessions") as batch_op:
        if has_column(conn, "install_sessions", "auto_detail"):
            batch_op.drop_column("auto_detail")
        if has_column(conn, "install_sessions", "auto_status"):
            batch_op.drop_column("auto_status")
        if has_column(conn, "install_sessions", "auto_mode"):
            batch_op.drop_column("auto_mode")
