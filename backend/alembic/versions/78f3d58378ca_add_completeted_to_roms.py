"""add completeted to roms

Revision ID: 78f3d58378ca
Revises: 0025_roms_hashes
Create Date: 2024-08-29 14:08:47.017055

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '78f3d58378ca'
down_revision = '0025_roms_hashes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("completed", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.drop_column("completed")
