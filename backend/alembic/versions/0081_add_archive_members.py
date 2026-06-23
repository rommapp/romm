"""Add archive_members JSON column to rom_files

Revision ID: 0081_add_archive_members
Revises: 0080_add_chd_sha1_hash
Create Date: 2026-05-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON

revision = "0081_add_archive_members"
down_revision = "0080_add_chd_sha1_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("archive_members", CustomJSON(), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_column("archive_members", if_exists=True)
