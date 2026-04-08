"""Add sync_sessions table and sync_config to devices

Revision ID: 0075_sync_sessions
Revises: 0074_fix_empty_json_arrays
Create Date: 2026-03-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM

from utils.database import is_postgresql

revision = "0075_sync_sessions"
down_revision = "0074_fix_empty_json_arrays"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if is_postgresql(connection):
        sync_session_status_enum = ENUM(
            "PENDING",
            "IN_PROGRESS",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            name="syncsessionstatus",
            create_type=False,
        )
        sync_session_status_enum.create(connection, checkfirst=True)
    else:
        sync_session_status_enum = sa.Enum(
            "PENDING",
            "IN_PROGRESS",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            name="syncsessionstatus",
        )

    op.create_table(
        "sync_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sync_session_status_enum,
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "initiated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "operations_planned", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "operations_completed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "operations_failed", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=(
                sa.text("CURRENT_TIMESTAMP")
                if is_postgresql(connection)
                else sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
            ),
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_sessions_device_id", "sync_sessions", ["device_id"])
    op.create_index("ix_sync_sessions_user_id", "sync_sessions", ["user_id"])
    op.create_index("ix_sync_sessions_status", "sync_sessions", ["status"])

    op.add_column("devices", sa.Column("sync_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "sync_config")

    op.drop_index("ix_sync_sessions_status", table_name="sync_sessions")

    op.drop_table("sync_sessions")

    connection = op.get_bind()
    if is_postgresql(connection):
        ENUM(name="syncsessionstatus").drop(connection, checkfirst=True)
