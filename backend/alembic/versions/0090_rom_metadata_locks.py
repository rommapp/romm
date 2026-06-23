"""Add metadata_locks column to roms for per-field metadata locking

Revision ID: 0090_rom_metadata_locks
Revises: 0089_client_tokens_device_id
Create Date: 2026-06-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0090_rom_metadata_locks"
down_revision = "0089_client_tokens_device_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "metadata_locks",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            ),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("metadata_locks", if_exists=True)
