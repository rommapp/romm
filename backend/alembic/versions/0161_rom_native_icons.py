"""Expose icons extracted from ROM binaries

Revision ID: 0161_rom_native_icons
Revises: 0160_state_origin_device
Create Date: 2026-11-10 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import column_names
from utils.roms_columns import ensure_roms_columns

revision = "0161_rom_native_icons"
down_revision = "0160_state_origin_device"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    ensure_roms_columns(conn)
    if "converto_read_at" in column_names(conn, "rom_files"):
        conn.execute(
            sa.text(
                "UPDATE rom_files SET converto_read_at = NULL "
                "WHERE converto_read_at IS NOT NULL"
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    if "path_icon" in column_names(conn, "roms"):
        op.drop_column("roms", "path_icon")
