"""Add play_sessions table for game time tracking

Revision ID: 0076_play_sessions
Revises: 0075_sync_sessions
Create Date: 2026-03-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0076_play_sessions"
down_revision = "0075_sync_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "play_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=True),
        sa.Column("rom_id", sa.Integer(), nullable=True),
        sa.Column("sync_session_id", sa.Integer(), nullable=True),
        sa.Column("save_slot", sa.String(length=255), nullable=True),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
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
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["sync_session_id"], ["sync_sessions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("play_sessions") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_play_sessions_user_rom"),
            ["user_id", "rom_id"],
        )
        batch_op.create_index(
            batch_op.f("ix_play_sessions_user_time"),
            ["user_id", "start_time"],
        )
        batch_op.create_index(
            "uq_play_session_identity",
            ["user_id", "device_id", "rom_id", "start_time"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("play_sessions") as batch_op:
        batch_op.drop_index("uq_play_session_identity")
        batch_op.drop_index(batch_op.f("ix_play_sessions_user_time"))
        batch_op.drop_index(batch_op.f("ix_play_sessions_user_rom"))
    op.drop_table("play_sessions")
