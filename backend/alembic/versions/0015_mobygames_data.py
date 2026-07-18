"""Add MobyGames data

Revision ID: 0015_mobygames_data
Revises: 0014_asset_files
Create Date: 2024-02-13 17:57:25.936825

"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON, is_postgresql

# revision identifiers, used by Alembic.
revision = "0015_mobygames_data"
down_revision = "0014_asset_files"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("moby_id", sa.Integer(), nullable=True), if_not_exists=True
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("moby_id", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("moby_metadata", CustomJSON(), nullable=True), if_not_exists=True
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        if is_postgresql(connection):
            batch_op.execute("update roms set moby_metadata = jsonb_build_object()")
        else:
            batch_op.execute("update roms set moby_metadata = JSON_OBJECT()")


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("moby_metadata", if_exists=True)
        batch_op.drop_column("moby_id", if_exists=True)

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("moby_id", if_exists=True)
