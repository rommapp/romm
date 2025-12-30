"""empty message

Revision ID: 0059_rom_version_tag
Revises: 0058_roms_metadata_launchbox
Create Date: 2025-12-30 10:48:45.025990

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0059_rom_version_tag"
down_revision = "0058_roms_metadata_launchbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("version", sa.String(length=100), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("version")
