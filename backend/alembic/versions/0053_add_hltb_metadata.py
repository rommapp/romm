"""Add HowLongToBeat metadata fields

Revision ID: 0053_add_hltb_metadata
Revises: 0052_roms_metadata_flashpoint
Create Date: 2025-09-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0053_add_hltb_metadata"
down_revision = "0052_roms_metadata_flashpoint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hltb_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "hltb_metadata",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            )
        )
        batch_op.create_index("idx_roms_hltb_id", ["hltb_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_hltb_id")
        batch_op.drop_column("hltb_metadata")
        batch_op.drop_column("hltb_id")
