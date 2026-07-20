"""Add physical-game columns to roms.

Revision ID: 0095_physical_roms
Revises: 0094_track_meta_table
Create Date: 2026-07-04 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0095_physical_roms"
down_revision = "0094_track_meta_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_physical",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("upc", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("upc")
        batch_op.drop_column("is_physical")
