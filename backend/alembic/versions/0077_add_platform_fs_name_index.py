"""Add composite index on (platform_id, fs_name) for roms table

Revision ID: 0077_add_platform_fs_name_index
Revises: 0076_play_sessions
Create Date: 2026-04-11 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0077_add_platform_fs_name_index"
down_revision = "0076_play_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            "idx_roms_platform_id_fs_name",
            ["platform_id", "fs_name"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_platform_id_fs_name")
