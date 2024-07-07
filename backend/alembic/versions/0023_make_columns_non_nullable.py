"""Make some columns non-nullable.

Revision ID: 0023_make_columns_non_nullable
Revises: 0022_collections
Create Date: 2024-07-07 13:44:25.811184

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0023_make_columns_non_nullable"
down_revision = "0022_collections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.execute("UPDATE platforms SET name = '' WHERE name IS NULL")
        batch_op.alter_column(
            "name", existing_type=sa.String(length=400), nullable=False
        )

    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.execute(
            "UPDATE rom_user SET note_is_public = 0 WHERE note_is_public IS NULL"
        )
        batch_op.alter_column(
            "note_is_public", existing_type=sa.Boolean(), nullable=False
        )
        batch_op.execute(
            "UPDATE rom_user SET is_main_sibling = 0 WHERE is_main_sibling IS NULL"
        )
        batch_op.alter_column(
            "is_main_sibling", existing_type=sa.Boolean(), nullable=False
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.execute("UPDATE roms SET multi = 0 WHERE multi IS NULL")
        batch_op.alter_column("multi", existing_type=sa.Boolean(), nullable=False)

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.execute("UPDATE users SET username = '' WHERE username IS NULL")
        batch_op.alter_column(
            "username", existing_type=sa.String(length=255), nullable=False
        )
        batch_op.execute("UPDATE users SET enabled = 0 WHERE enabled IS NULL")
        batch_op.alter_column("enabled", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("enabled", existing_type=sa.Boolean(), nullable=True)
        batch_op.alter_column(
            "username", existing_type=sa.String(length=255), nullable=True
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column("multi", existing_type=sa.Boolean(), nullable=True)

    with op.batch_alter_table("rom_user", schema=None) as batch_op:
        batch_op.alter_column(
            "is_main_sibling", existing_type=sa.Boolean(), nullable=True
        )
        batch_op.alter_column(
            "note_is_public", existing_type=sa.Boolean(), nullable=True
        )

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.alter_column(
            "name", existing_type=sa.String(length=400), nullable=True
        )
