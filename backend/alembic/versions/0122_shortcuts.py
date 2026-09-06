"""Add shortcuts table and devices.launch_capabilities.

``shortcuts`` records which games a user wants in a launcher (Steam via the
desktop companion) on one paired device, and where each row is in the
add/remove lifecycle. ``devices.launch_capabilities`` holds the per-platform
emulator map a launcher client reports so the UI can refuse an add up front.

Revision ID: 0122_shortcuts
Revises: 0121_state_disc_file
Create Date: 2026-09-06 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0122_shortcuts"
down_revision = "0121_state_disc_file"
branch_labels = None
depends_on = None

# SQLAlchemy stores enum member names, matching the other enum columns.
SHORTCUT_STATUSES = ("PENDING_ADD", "STAGED", "ADDED", "PENDING_REMOVE", "FAILED")
LAUNCH_MODES = ("EMULATOR", "WEB_PLAYER")


def upgrade() -> None:
    op.create_table(
        "shortcuts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*SHORTCUT_STATUSES, name="shortcutstatus"),
            nullable=False,
        ),
        sa.Column(
            "launch_mode",
            sa.Enum(*LAUNCH_MODES, name="launchmode"),
            nullable=True,
        ),
        sa.Column("steam_app_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "rom_id", name="uq_shortcuts_device_rom"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_shortcuts_device_id", "shortcuts", ["device_id"], if_not_exists=True
    )
    op.create_index("ix_shortcuts_rom_id", "shortcuts", ["rom_id"], if_not_exists=True)

    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("launch_capabilities", CustomJSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("devices", schema=None) as batch_op:
        batch_op.drop_column("launch_capabilities")

    # MariaDB refuses to drop an index a foreign key relies on; dropping the
    # table removes the indexes with it.
    op.drop_table("shortcuts")
    # Enum types are standalone objects on PostgreSQL only.
    sa.Enum(name="shortcutstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="launchmode").drop(op.get_bind(), checkfirst=True)
