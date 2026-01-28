"""Add indexes on updated_at for collections and smart_collections tables

Revision ID: 0065_collections_updated_at_idx
Revises: 0064_add_updated_at_indexes
Create Date: 2026-01-17

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0065_collections_updated_at_idx"
down_revision = "0064_add_updated_at_indexes"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.create_index("ix_collections_updated_at", ["updated_at"], unique=False)

    with op.batch_alter_table("smart_collections", schema=None) as batch_op:
        batch_op.create_index(
            "ix_smart_collections_updated_at", ["updated_at"], unique=False
        )


def downgrade():
    with op.batch_alter_table("collections", schema=None) as batch_op:
        batch_op.drop_index("ix_collections_updated_at")

    with op.batch_alter_table("smart_collections", schema=None) as batch_op:
        batch_op.drop_index("ix_smart_collections_updated_at")
