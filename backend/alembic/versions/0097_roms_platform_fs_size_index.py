"""Add composite index on roms (platform_id, fs_size_bytes)

GET /api/platforms and GET /api/stats both sum roms.fs_size_bytes (per platform
and across the whole library). fs_size_bytes was not part of any index, so the
database had to read actual rows from the very wide, JSON-heavy roms table,
taking 5-11s on large libraries. This composite index lets both sums resolve as
index-only scans that never touch the wide rows; the optimizer picks it for both
query shapes on its own.

Revision ID: 0097_roms_platform_fs_size_index
Revises: 0096_fix_virtual_collections
Create Date: 2026-07-16 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0097_roms_platform_fs_size_index"
down_revision = "0096_fix_virtual_collections"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_roms_platform_fs_size"
INDEX_COLUMNS = ["platform_id", "fs_size_bytes"]


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            INDEX_NAME,
            INDEX_COLUMNS,
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
