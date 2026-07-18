"""Add Launchbox data and remove RetroAchievements metadata from rom_user

Revision ID: 0043_launchbox_id
Revises: 0042_add_missing_from_fs
Create Date: 2025-05-20 22:39:16.993191

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from utils.database import CustomJSON

revision = "0043_launchbox_id"
down_revision = "0042_add_missing_from_fs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.drop_column("ra_metadata", if_exists=True)

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("launchbox_id", sa.Integer(), nullable=True), if_not_exists=True
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("launchbox_id", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column(
                "launchbox_metadata",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            ),
            if_not_exists=True,
        )
        batch_op.create_index(
            "idx_roms_launchbox_id", ["launchbox_id"], unique=False, if_not_exists=True
        )
        batch_op.create_index(
            "idx_roms_ra_id", ["ra_id"], unique=False, if_not_exists=True
        )
        batch_op.create_index(
            "idx_roms_sgdb_id", ["sgdb_id"], unique=False, if_not_exists=True
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_sgdb_id", if_exists=True)
        batch_op.drop_index("idx_roms_ra_id", if_exists=True)
        batch_op.drop_index("idx_roms_launchbox_id", if_exists=True)
        batch_op.drop_column("launchbox_metadata", if_exists=True)
        batch_op.drop_column("launchbox_id", if_exists=True)

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("launchbox_id", if_exists=True)

    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ra_metadata", CustomJSON(), nullable=True), if_not_exists=True
        )
