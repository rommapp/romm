"""Add the per-file serial and feature flags sigil reads, which a restore needs.

Revision ID: 0151_rom_file_sigil_identity
Revises: 0150_link_slots_to_channels
Create Date: 2026-10-07 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision = "0151_rom_file_sigil_identity"
down_revision = "0150_link_slots_to_channels"
branch_labels = None
depends_on = None


def _columns() -> list[sa.Column]:
    return [
        sa.Column("raw_serial", sa.String(length=100), nullable=True),
        sa.Column("sigil_features", sa.BigInteger(), nullable=True),
    ]


def upgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        for column in _columns():
            batch_op.add_column(column, if_not_exists=True)


def downgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        for column in reversed(_columns()):
            batch_op.drop_column(column.name, if_exists=True)
