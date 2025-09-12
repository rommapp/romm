"""Add smart collections table

Revision ID: 0047_smart_collections
Revises: 0046_migrate_platform_slugs
Create Date: 2024-12-19 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0047_smart_collections"
down_revision = "0046_migrate_platform_slugs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create smart collections table (no association table - purely computed)."""

    # Create the smart collections table
    op.create_table(
        "smart_collections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=400), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, default=False),
        sa.Column("filter_criteria", CustomJSON(), nullable=False, default={}),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rom_count", sa.Integer(), nullable=False, default=0),
        sa.Column(
            "rom_ids",
            CustomJSON(),
            nullable=False,
            default=[],
        ),
        sa.Column("path_covers_small", CustomJSON(), nullable=False, default=[]),
        sa.Column("path_covers_large", CustomJSON(), nullable=False, default=[]),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop smart collections table."""

    op.drop_table("smart_collections")
