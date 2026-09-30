"""Remote install sessions.

Revision ID: 0106_install_sessions
Revises: 0105_fix_gamelist_epoch_ms
Create Date: 2026-09-14 00:00:00.000000

Tracks one remote-install run per rom+user: which installer was picked, the
sandbox/VNC working state, live byte progress for streaming to clients, and
the on-disk cache TTL.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0144_install_sessions"
down_revision = "0146_roms_search_aliases"
branch_labels = None
depends_on = None

# Kept in sync with models.install_session.InstallSessionState. Stored as a
# plain VARCHAR (native_enum=False) so new states don't need a cross-dialect
# ALTER TYPE migration later.
INSTALL_SESSION_STATES = (
    "detecting",
    "awaiting_installer",
    "installing",
    "streaming",
    "done",
    "failed",
    "expired",
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "install_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                *INSTALL_SESSION_STATES,
                name="install_session_state",
                native_enum=False,
                length=32,
            ),
            nullable=False,
            server_default="detecting",
        ),
        sa.Column("installer_path", sa.String(length=1000), nullable=True),
        sa.Column("cache_path", sa.String(length=1000), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("vnc_url", sa.String(length=500), nullable=True),
        sa.Column("vnc_web_port", sa.Integer(), nullable=True),
        sa.Column(
            "bytes_written",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "bytes_total",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("job_id", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_install_sessions_rom",
        "install_sessions",
        ["rom_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_install_sessions_user",
        "install_sessions",
        ["user_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_install_sessions_state",
        "install_sessions",
        ["state"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("install_sessions", if_exists=True)
