"""empty message

Revision ID: 0042_add_missing_from_fs
Revises: 0041_assets_t_thumb_cleanup
Create Date: 2025-06-11

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0042_add_missing_from_fs"
down_revision = "0041_assets_t_thumb_cleanup"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "missing_from_fs", sa.Boolean(), nullable=False, server_default="0"
            )
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "missing_from_fs", sa.Boolean(), nullable=False, server_default="0"
            )
        )

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "missing_from_fs", sa.Boolean(), nullable=False, server_default="0"
            )
        )

    with op.batch_alter_table("firmware", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "missing_from_fs", sa.Boolean(), nullable=False, server_default="0"
            )
        )

    with op.batch_alter_table("saves", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "missing_from_fs", sa.Boolean(), nullable=False, server_default="0"
            )
        )

    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "missing_from_fs", sa.Boolean(), nullable=False, server_default="0"
            )
        )

    with op.batch_alter_table("screenshots", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "missing_from_fs", sa.Boolean(), nullable=False, server_default="0"
            )
        )


def downgrade():
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("missing_from_fs")

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("missing_from_fs")

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_column("missing_from_fs")

    with op.batch_alter_table("firmware", schema=None) as batch_op:
        batch_op.drop_column("missing_from_fs")

    with op.batch_alter_table("saves", schema=None) as batch_op:
        batch_op.drop_column("missing_from_fs")

    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.drop_column("missing_from_fs")

    with op.batch_alter_table("screenshots", schema=None) as batch_op:
        batch_op.drop_column("missing_from_fs")
