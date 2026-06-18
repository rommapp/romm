"""Add is_gallery + is_public flags to screenshots for per-user community
gallery screenshots (distinct from auto-captured save/state thumbnails).

Revision ID: 0085_screenshot_visibility
Revises: 0084_rom_category_screenshot
Create Date: 2026-06-18 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0085_screenshot_visibility"
down_revision = "0084_rom_category_screenshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "screenshots",
        sa.Column(
            "is_gallery",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        if_not_exists=True,
    )
    op.add_column(
        "screenshots",
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        if_not_exists=True,
    )
    op.create_index(
        "idx_screenshots_public", "screenshots", ["is_public"], if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("idx_screenshots_public", table_name="screenshots", if_exists=True)
    op.drop_column("screenshots", "is_public", if_exists=True)
    op.drop_column("screenshots", "is_gallery", if_exists=True)
