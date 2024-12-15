"""add retro achievements data

Revision ID: 0028_add_retro_achievements
Revises: 0027_platforms_data
Create Date: 2024-08-31 18:48:49.772416

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0028_add_retro_achievements"
down_revision = "0027_platforms_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ra_metadata", mysql.JSON(), nullable=True))

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ra_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ra_api_key", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ra_username", sa.String(length=100), nullable=True)
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ra_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.drop_column("ra_metadata")

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("ra_id")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("ra_api_key")
        batch_op.drop_column("ra_username")

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("ra_id")
