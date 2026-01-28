"""Add indexes on updated_at for roms and platforms tables

Revision ID: 0064_add_updated_at_indexes
Revises: 0063_roms_metadata_player_count
Create Date: 2026-01-12

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0064_add_updated_at_indexes"
down_revision = "0063_roms_metadata_player_count"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index("ix_roms_updated_at", ["updated_at"], unique=False)

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.create_index("ix_platforms_updated_at", ["updated_at"], unique=False)


def downgrade():
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("ix_roms_updated_at")

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_index("ix_platforms_updated_at")
