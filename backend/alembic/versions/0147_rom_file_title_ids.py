"""Add the per-file title id columns rom-converto fills on rom_files.

Revision ID: 0147_rom_file_title_ids
Revises: 0146_roms_search_aliases
Create Date: 2026-10-02 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision = "0147_rom_file_title_ids"
down_revision = "0146_roms_search_aliases"
branch_labels = None
depends_on = None


def _columns() -> list[sa.Column]:
    return [
        sa.Column("title_id", sa.String(length=100), nullable=True),
        # BigInteger: Switch title versions are u32 and can exceed signed int32.
        sa.Column("title_version", sa.BigInteger(), nullable=True),
        sa.Column("converto_read_at", sa.TIMESTAMP(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        for column in _columns():
            batch_op.add_column(column, if_not_exists=True)


def downgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        for column in reversed(_columns()):
            batch_op.drop_column(column.name, if_exists=True)
