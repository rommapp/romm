"""Add guide book columns to roms

Revision ID: 0083_add_guide_to_roms
Revises: 0082_save_origin_device
Create Date: 2026-06-15 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0083_add_guide_to_roms"
down_revision = "0082_save_origin_device"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("url_guide", sa.Text(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("path_guide", sa.Text(), nullable=True), if_not_exists=True
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("url_guide", if_exists=True)
        batch_op.drop_column("path_guide", if_exists=True)
