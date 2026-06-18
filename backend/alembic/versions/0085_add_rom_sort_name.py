"""Add sort_name column to roms

Revision ID: 0085_add_rom_sort_name
Revises: 0084_add_roms_search_index
Create Date: 2026-05-31 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0085_add_rom_sort_name"
down_revision = "0084_add_roms_search_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("sort_name", sa.String(length=350), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("sort_name", if_exists=True)
