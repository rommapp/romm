"""Add the per-user pinned overview media

Revision ID: 0137_rom_user_pinned_media
Revises: 0136_deleted_assets
Create Date: 2026-09-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0137_rom_user_pinned_media"
down_revision = "0136_deleted_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rom_user",
        sa.Column("pinned_media", CustomJSON(), nullable=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("rom_user", "pinned_media", if_exists=True)
