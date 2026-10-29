"""Index `roms` by platform and `min_age` for age-limited platform totals

Revision ID: 0156_roms_platform_min_age_index
Revises: 0155_retired_arcade_slugs
Create Date: 2026-10-29 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0156_roms_platform_min_age_index"
down_revision = "0155_retired_arcade_slugs"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_roms_platform_min_age"


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            INDEX_NAME,
            ["platform_id", "min_age", "fs_size_bytes"],
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
