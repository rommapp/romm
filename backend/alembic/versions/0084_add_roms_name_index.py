"""Add index on roms.name

Revision ID: 0084_add_roms_name_index
Revises: 0083_add_roms_search_indexes
Create Date: 2026-06-16 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0084_add_roms_name_index"
down_revision = "0083_add_roms_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            "idx_roms_name",
            ["name"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_name", if_exists=True)
