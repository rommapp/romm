"""Add is_virtual flag to roms

Revision ID: 0104_roms_is_virtual
Revises: 0103_roms_facets_provider_ids
Create Date: 2026-07-23

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0104_roms_is_virtual"
down_revision = "0103_roms_facets_provider_ids"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default="0"),
            if_not_exists=True,
        )


def downgrade():
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("is_virtual", if_exists=True)
