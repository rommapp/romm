"""empty message

Revision ID: 0049_add_fs_size_bytes
Revises: 0048_sibling_roms_more_ids
Create Date: 2025-08-20 01:14:05.164201

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0049_add_fs_size_bytes"
down_revision = "0048_sibling_roms_more_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("fs_size_bytes", sa.BigInteger(), nullable=True))

    # Set fs_size_bytes for all roms
    op.execute(
        sa.text(
            "UPDATE roms SET fs_size_bytes = COALESCE((SELECT SUM(file_size_bytes) FROM rom_files WHERE roms.id = rom_files.rom_id), 0)"
        )
    )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "fs_size_bytes", existing_type=sa.BigInteger(), nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("fs_size_bytes")
