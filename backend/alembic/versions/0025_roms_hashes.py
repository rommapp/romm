"""Add hashes to roms

Revision ID: 0025_roms_hashes
Revises: 0024_sibling_roms_db_view
Create Date: 2024-08-11 21:50:53.301352

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0025_roms_hashes"
down_revision = "0024_sibling_roms_db_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("crc_hash", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("md5_hash", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("sha1_hash", sa.String(length=100), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("sha1_hash")
        batch_op.drop_column("md5_hash")
        batch_op.drop_column("crc_hash")
