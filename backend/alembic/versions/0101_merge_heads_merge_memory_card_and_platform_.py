"""merge memory card and platform description heads

Revision ID: 0101_merge_heads
Revises: 0099_platform_description, 0100_container_adoptions
Create Date: 2026-07-21 16:45:14.684739

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0101_merge_heads"
down_revision = ("0099_platform_description", "0100_container_adoptions")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
