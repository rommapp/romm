"""Add the audit_events table

One row per thing a user, or RomM itself, did: plays, downloads, library and
collection changes, scans, tasks, sign-ins and account changes. Admins read it
as the audit log.

Revision ID: 0132_audit_events
Revises: 0131_notification_channels
Create Date: 2026-09-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0132_audit_events"
down_revision = "0131_notification_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actor_kind", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("target_name", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("device_id", sa.String(length=255), nullable=True),
        sa.Column("data", CustomJSON(), nullable=False),
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
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_audit_events_occurred_at",
        "audit_events",
        ["occurred_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_audit_events_actor_occurred",
        "audit_events",
        ["actor_id", "occurred_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_audit_events_target",
        "audit_events",
        ["target_type", "target_id", "occurred_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_audit_events_action_occurred",
        "audit_events",
        ["action", "occurred_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    # The indexes back the foreign key, so they go with the table.
    op.drop_table("audit_events", if_exists=True)
