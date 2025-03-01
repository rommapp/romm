"""empty message

Revision ID: 0037_drop_platform_url
Revises: 0036_screenscraper_platforms_id
Create Date: 2025-03-01 16:42:16.618676

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0037_drop_platform_url"
down_revision = "0036_screenscraper_platforms_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("url")
        batch_op.drop_column("logo_path")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=postgresql.ENUM("VIEWER", "EDITOR", "ADMIN", name="role"),
            nullable=False,
        )
        batch_op.alter_column(
            "avatar_path", existing_type=sa.VARCHAR(length=255), nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "avatar_path", existing_type=sa.VARCHAR(length=255), nullable=True
        )
        batch_op.alter_column(
            "role",
            existing_type=postgresql.ENUM("VIEWER", "EDITOR", "ADMIN", name="role"),
            nullable=True,
        )

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "url", sa.VARCHAR(length=1000), autoincrement=False, nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                "logo_path", sa.VARCHAR(length=1000), autoincrement=False, nullable=True
            )
        )
