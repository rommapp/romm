"""empty message
Revision ID: 0057_add_giantbomb_metadata
Revises: 0056_gamelist_xml
Create Date: 2025-09-19 21:37:14.878761
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0057_add_giantbomb_metadata"
down_revision = "0056_gamelist_xml"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("giantbomb_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("giantbomb_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "giantbomb_metadata",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            )
        )
        batch_op.create_index("idx_roms_giantbomb_id", ["giantbomb_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_giantbomb_id")
        batch_op.drop_column("giantbomb_metadata")
        batch_op.drop_column("giantbomb_id")
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("giantbomb_id")
