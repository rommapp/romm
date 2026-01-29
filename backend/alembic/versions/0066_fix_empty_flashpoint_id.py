"""Fix empty string flashpoint_id values by setting them to NULL

Revision ID: 0066_fix_empty_flashpoint_id
Revises: 0065_collections_updated_at_idx
Create Date: 2026-01-18

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0066_fix_empty_flashpoint_id"
down_revision = "0065_collections_updated_at_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE roms SET flashpoint_id = NULL WHERE flashpoint_id = ''")


def downgrade():
    # Cannot restore empty strings - they should have been NULL originally
    pass
