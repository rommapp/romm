"""Add physical-game columns to roms.

Revision ID: 0111_physical_roms
Revises: 0110_walkthrough_docs
Create Date: 2026-07-04 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import has_column

# revision identifiers, used by Alembic.
revision = "0111_physical_roms"
down_revision = "0110_walkthrough_docs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    # A batch emits one ALTER per column on MySQL/MariaDB, so the second can
    # fail with the first already committed.
    with op.batch_alter_table("roms", schema=None) as batch_op:
        if not has_column(connection, "roms", "is_physical"):
            batch_op.add_column(
                sa.Column(
                    "is_physical",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
        if not has_column(connection, "roms", "upc"):
            batch_op.add_column(sa.Column("upc", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("upc")
        batch_op.drop_column("is_physical")
