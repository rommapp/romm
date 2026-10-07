"""Index lowercased `roms.fs_name_no_ext` on PostgreSQL for Cloud Sync's ROM lookup

Revision ID: 0150_roms_fs_name_lower_index
Revises: 0149_roms_fs_name_no_ext_index
Create Date: 2026-10-07 00:00:00.000000

"""

from alembic import op

from utils.database import ROMS_FS_NAME_NO_EXT_LOWER_INDEX, is_postgresql

# revision identifiers, used by Alembic.
revision = "0150_roms_fs_name_lower_index"
down_revision = "0149_roms_fs_name_no_ext_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if is_postgresql(op.get_bind()):
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {ROMS_FS_NAME_NO_EXT_LOWER_INDEX} "
            "ON roms (lower(fs_name_no_ext))"
        )


def downgrade() -> None:
    if is_postgresql(op.get_bind()):
        op.execute(f"DROP INDEX IF EXISTS {ROMS_FS_NAME_NO_EXT_LOWER_INDEX}")
