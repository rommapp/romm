"""Add natural pixel dimensions of the large cover to roms so the frontend
can render cover art at its natural aspect ratio instead of a forced box.

Columns are nullable: remote-only covers and rows scanned before this change
have no value and the client falls back to the default box-art ratio. A
background backfill fills them for existing local covers.

Revision ID: 0087_cover_dimensions
Revises: 0086_screenshot_visibility
Create Date: 2026-06-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0087_cover_dimensions"
down_revision = "0086_screenshot_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roms",
        sa.Column("cover_width", sa.Integer(), nullable=True),
        if_not_exists=True,
    )
    op.add_column(
        "roms",
        sa.Column("cover_height", sa.Integer(), nullable=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("roms", "cover_height", if_exists=True)
    op.drop_column("roms", "cover_width", if_exists=True)
