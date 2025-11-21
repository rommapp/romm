"""empty message

Revision ID: 0054_add_platform_metadata_slugs
Revises: 0053_add_hltb_metadata
Create Date: 2025-09-22 21:42:33.654137

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0054_add_platform_metadata_slugs"
down_revision = "0053_add_hltb_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(sa.Column("flashpoint_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("igdb_slug", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("moby_slug", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column("hltb_slug", sa.String(length=100), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("hltb_slug")
        batch_op.drop_column("moby_slug")
        batch_op.drop_column("igdb_slug")
        batch_op.drop_column("flashpoint_id")
