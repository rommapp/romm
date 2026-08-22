"""Cover the rom_files category lookups

`rom_files` is indexed on `rom_id` alone, so resolving `has_soundtrack` for a
ROM without one walks every file row that ROM owns and reads `category` off the
clustered index for each. The `has_soundtrack` gallery filter has no index at
all. Both are served by the composite.

Revision ID: 0109_rom_files_category_index
Revises: 0108_roms_primary_region
Create Date: 2026-08-22 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0109_rom_files_category_index"
down_revision = "0108_roms_primary_region"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_rom_files_rom_id_category"
INDEX_COLUMNS = ["rom_id", "category"]


def upgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.create_index(
            INDEX_NAME,
            INDEX_COLUMNS,
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
