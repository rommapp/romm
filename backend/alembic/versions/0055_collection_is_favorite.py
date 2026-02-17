"""Add is_favorite to collections

Revision ID: 0055_collection_is_favorite
Revises: 0054_add_platform_metadata_slugs
Create Date: 2025-10-18 13:24:15.119652

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0055_collection_is_favorite"
down_revision = "0054_add_platform_metadata_slugs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_favorite", sa.Boolean(), nullable=True))

    op.execute("UPDATE collections SET is_favorite = FALSE WHERE is_favorite IS NULL")
    op.execute("""
        UPDATE collections
        SET is_favorite = TRUE
        WHERE LOWER(name) IN ('favourites', 'favorites')
        """)

    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.alter_column("is_favorite", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.drop_column("is_favorite")
