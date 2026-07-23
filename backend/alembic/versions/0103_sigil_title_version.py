"""Add sigil-extracted title_version column to rom_files (Switch title
versions are u32, stored as BigInteger).

Revision ID: 0103_sigil_title_version
Revises: 0102_sigil_title_ids
Create Date: 2026-07-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0103_sigil_title_version"
down_revision = "0102_sigil_title_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rom_files",
        sa.Column("title_version", sa.BigInteger(), nullable=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("rom_files", "title_version", if_exists=True)
