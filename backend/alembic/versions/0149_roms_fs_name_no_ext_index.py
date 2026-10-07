"""Index `roms.fs_name_no_ext` for RetroArch Cloud Sync's ROM lookup

Revision ID: 0149_roms_fs_name_no_ext_index
Revises: 0148_rom_age_limits
Create Date: 2026-10-06 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0149_roms_fs_name_no_ext_index"
down_revision = "0148_rom_age_limits"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_roms_fs_name_no_ext"


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(INDEX_NAME, ["fs_name_no_ext"], if_not_exists=True)


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
