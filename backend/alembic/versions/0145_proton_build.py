"""Add proton_build to install_sessions.

Revision ID: 0107_proton_build
Revises: 0106_install_sessions
Create Date: 2026-09-16 00:00:00.000000

Proton build id chosen per install run (see handler.install.proton_builds).
NULL keeps today's behaviour: fall back to the server default
(INSTALL_PROTON_PATH).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0145_proton_build"
down_revision = "0144_install_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("install_sessions") as batch_op:
        batch_op.add_column(
            sa.Column("proton_build", sa.String(length=255), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("install_sessions") as batch_op:
        batch_op.drop_column("proton_build")
