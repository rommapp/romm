"""Add chd_sha1_hash to rom_files

Revision ID: 0079_add_chd_sha1_hash_to_rom_files
Revises: 0078_add_libretro_id_to_roms
Create Date: 2026-04-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0079_add_chd_sha1_hash_to_rom_files"
down_revision = "0078_add_libretro_id_to_roms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("chd_sha1_hash", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_column("chd_sha1_hash", if_exists=True)
