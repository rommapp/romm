"""empty message

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
    # Add column as nullable first
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_favorite", sa.Boolean(), nullable=True))

    # Set default value for all existing rows
    op.execute("UPDATE collections SET is_favorite = FALSE WHERE is_favorite IS NULL")

    # Find favorite collection and set is_favorite to True
    from handler.database import db_collection_handler, db_user_handler

    users = db_user_handler.get_users()
    for user in users:
        collection = db_collection_handler.get_collection_by_name("favourites", user.id)
        if not collection:
            collection = db_collection_handler.get_collection_by_name(
                "favorites", user.id
            )

        if collection:
            db_collection_handler.update_collection(
                collection.id, {"is_favorite": True}
            )

    # Now make the column non-nullable
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.alter_column("is_favorite", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.drop_column("is_favorite")
