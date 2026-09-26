"""Add the notification_channels table.

Revision ID: 0131_notification_channels
Revises: 0130_notifications
Create Date: 2026-09-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0131_notification_channels"
down_revision = "0130_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("config", sa.Text(), nullable=False),
        sa.Column("min_level", sa.String(length=16), nullable=False),
        sa.Column("topics", CustomJSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_notification_channels_user_id",
        "notification_channels",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    # The index backs the foreign key, so it goes with the table.
    op.drop_table("notification_channels", if_exists=True)
