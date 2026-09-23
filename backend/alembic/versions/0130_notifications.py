"""Add the notifications table

Persistent per-user notifications, kept until the user dismisses them, so what
a background job or another user did reaches them the next time they open RomM.

Revision ID: 0130_notifications
Revises: 0129_save_state_favorites_labels
Create Date: 2026-09-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0130_notifications"
down_revision = "0129_save_state_favorites_labels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("data", CustomJSON(), nullable=True),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_notifications_actor_id",
        "notifications",
        ["actor_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    # The indexes back the foreign keys, so they go with the table.
    op.drop_table("notifications", if_exists=True)
