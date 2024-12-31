"""empty message

Revision ID: 0026_romuser_status_fields
Revises: 0025_roms_hashes
Create Date: 2024-08-29 15:52:56.031850

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM
from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0026_romuser_status_fields"
down_revision = "0025_roms_hashes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.alter_column(
            "path_cover_l",
            existing_type=sa.VARCHAR(length=1000),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "path_cover_s",
            existing_type=sa.VARCHAR(length=1000),
            type_=sa.Text(),
            existing_nullable=True,
        )

    if is_postgresql(connection):
        rom_user_status_enum = ENUM(
            "INCOMPLETE",
            "FINISHED",
            "COMPLETED_100",
            "RETIRED",
            "NEVER_PLAYING",
            name="romuserstatus",
            create_type=False,
        )
        rom_user_status_enum.create(connection, checkfirst=False)
    else:
        rom_user_status_enum = sa.Enum(
            "INCOMPLETE",
            "FINISHED",
            "COMPLETED_100",
            "RETIRED",
            "NEVER_PLAYING",
            name="romuserstatus",
        )

    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("last_played", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("backlogged", sa.Boolean(), nullable=False))
        batch_op.add_column(sa.Column("now_playing", sa.Boolean(), nullable=False))
        batch_op.add_column(sa.Column("hidden", sa.Boolean(), nullable=False))
        batch_op.add_column(sa.Column("rating", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("difficulty", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("completion", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("status", rom_user_status_enum, nullable=True))


def downgrade() -> None:
    connection = op.get_bind()

    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.drop_column("status")
        batch_op.drop_column("completion")
        batch_op.drop_column("difficulty")
        batch_op.drop_column("rating")
        batch_op.drop_column("hidden")
        batch_op.drop_column("now_playing")
        batch_op.drop_column("backlogged")
        batch_op.drop_column("last_played")

    if is_postgresql(connection):
        ENUM(name="romuserstatus").drop(connection, checkfirst=False)

    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.alter_column(
            "path_cover_s",
            existing_type=sa.Text(),
            type_=sa.VARCHAR(length=1000),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "path_cover_l",
            existing_type=sa.Text(),
            type_=sa.VARCHAR(length=1000),
            existing_nullable=True,
        )
