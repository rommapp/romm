"""Add source_path, phase and phase_detail to install_sessions.

Revision ID: 0148_install_source_phase
Revises: 0147_proton_build
Create Date: 2026-09-25 00:00:00.000000

source_path: archive or disc image (relative to the ROM directory) the
installer is extracted from. phase/phase_detail: what the worker is doing
before the VNC bridge is up ("extracting"/"mounting" plus the file name).
"""

import sqlalchemy as sa
from alembic import op

from utils.database import has_column

# revision identifiers, used by Alembic.
revision = "0148_install_source_phase"
down_revision = "0147_proton_build"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("install_sessions") as batch_op:
        # Guarded individually: a MariaDB/MySQL crash between two of these
        # ADD COLUMNs (each auto-commits on its own) would otherwise replay
        # the whole revision and fail re-adding the one that already landed.
        if not has_column(conn, "install_sessions", "source_path"):
            batch_op.add_column(
                sa.Column("source_path", sa.String(length=1000), nullable=True)
            )
        if not has_column(conn, "install_sessions", "phase"):
            batch_op.add_column(sa.Column("phase", sa.String(length=32), nullable=True))
        if not has_column(conn, "install_sessions", "phase_detail"):
            batch_op.add_column(
                sa.Column("phase_detail", sa.String(length=1000), nullable=True)
            )


def downgrade() -> None:
    conn = op.get_bind()
    with op.batch_alter_table("install_sessions") as batch_op:
        if has_column(conn, "install_sessions", "phase_detail"):
            batch_op.drop_column("phase_detail")
        if has_column(conn, "install_sessions", "phase"):
            batch_op.drop_column("phase")
        if has_column(conn, "install_sessions", "source_path"):
            batch_op.drop_column("source_path")
