"""empty message

Revision ID: 0051_flashpoint_metadata
Revises: 0050_firmware_add_is_verified
Create Date: 2025-08-27 16:53:19.567809

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0051_flashpoint_metadata"
down_revision = "0050_firmware_add_is_verified"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("flashpoint_id", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "flashpoint_metadata",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            )
        )
        batch_op.create_index("idx_roms_flashpoint_id", ["flashpoint_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_flashpoint_id")
        batch_op.drop_column("flashpoint_metadata")
        batch_op.drop_column("flashpoint_id")
