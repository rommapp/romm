"""empty message

Revision ID: 0042_add_missing_fields
Revises: 0041_assets_t_thumb_cleanup
Create Date: 2025-06-11

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0042_add_missing_fields"
down_revision = "0041_assets_t_thumb_cleanup"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("missing", sa.Boolean(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("missing", sa.Boolean(), nullable=False, server_default="0")
        )


def downgrade():
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("missing")

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("missing")
