"""

Revision ID: 0056_gamelist_xml
Revises: 0055_collection_is_favorite
Create Date: 2025-10-16 23:07:05.145056

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0056_gamelist_xml"
down_revision = "0055_collection_is_favorite"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("gamelist_id", sa.String(length=100), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "gamelist_metadata",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            )
        )
        batch_op.create_index("idx_roms_gamelist_id", ["gamelist_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_gamelist_id")
        batch_op.drop_column("gamelist_metadata")
        batch_op.drop_column("gamelist_id")
