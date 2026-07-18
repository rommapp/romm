"""add retro achievements data

Revision ID: 0039_add_retro_achievements
Revises: 0038_add_ssid_to_sibling_roms
Create Date: 2025-04-11 00:59:30.772416

"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0039_add_retro_achievements"
down_revision = "0038_add_ssid_to_sibling_roms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ra_metadata", CustomJSON(), nullable=True), if_not_exists=True
        )

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ra_hash", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ra_id", sa.Integer(), nullable=True), if_not_exists=True
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ra_username", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("ra_progression", CustomJSON(), nullable=True), if_not_exists=True
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ra_id", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("ra_hash", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("ra_metadata", CustomJSON(), nullable=True), if_not_exists=True
        )


def downgrade() -> None:
    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.drop_column("ra_metadata", if_exists=True)

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("ra_id", if_exists=True)

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("ra_username", if_exists=True)
        batch_op.drop_column("ra_progression", if_exists=True)

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("ra_id", if_exists=True)
        batch_op.drop_column("ra_hash", if_exists=True)
        batch_op.drop_column("ra_metadata", if_exists=True)

    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_column("ra_hash", if_exists=True)
