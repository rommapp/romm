"""user_ui_settings

Revision ID: 0058_user_ui_settings
Revises: 0059_rom_version_tag
Create Date: 2025-12-16 21:02:52.394533

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0058_user_ui_settings"
down_revision = "0059_rom_version_tag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add ui_settings column to users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "ui_settings",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            )
        )


def downgrade() -> None:
    """Remove ui_settings column from users table."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("ui_settings")
