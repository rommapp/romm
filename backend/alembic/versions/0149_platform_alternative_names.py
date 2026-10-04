"""Add IGDB's abbreviation and alternative name to platforms

Revision ID: 0149_platform_alternative_names
Revises: 0148_rom_age_limits
Create Date: 2026-10-04 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0149_platform_alternative_names"
down_revision = "0148_rom_age_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("abbreviation", sa.String(length=100), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("alternative_name", sa.String(length=400), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("alternative_name", if_exists=True)
        batch_op.drop_column("abbreviation", if_exists=True)
