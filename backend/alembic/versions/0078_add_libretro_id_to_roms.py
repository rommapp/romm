"""Add libretro_id to roms

Revision ID: 0078_add_libretro_id_to_roms
Revises: 0077_add_platform_fs_name_index
Create Date: 2026-04-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0078_add_libretro_id_to_roms"
down_revision = "0077_add_platform_fs_name_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("libretro_id", sa.String(length=64), nullable=True),
            if_not_exists=True,
        )
        batch_op.create_index(
            "idx_roms_libretro_id",
            ["libretro_id"],
            unique=False,
            if_not_exists=True,
        )

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("libretro_slug", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_libretro_id", if_exists=True)
        batch_op.drop_column("libretro_id", if_exists=True)

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("libretro_slug", if_exists=True)
