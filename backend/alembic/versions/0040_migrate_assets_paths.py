"""migrate save file paths to include rom_id

Revision ID: 0040_migrate_assets_paths
Revises: 0039_add_retro_achievements
Create Date: 2025-05-14 18:10:23.522345
"""

import os

from alembic import op
from config import ASSETS_BASE_PATH
from logger.logger import log
from sqlalchemy.sql import text
from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0040_migrate_assets_paths"
down_revision = "0039_add_retro_achievements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    is_pg = is_postgresql(conn)

    if is_pg:
        like_clause = "file_path NOT LIKE '%%/' || rom_id::text || '/%%'"
    else:
        like_clause = "file_path NOT LIKE CONCAT('%/', rom_id, '/%')"

    results = conn.execute(
        text(
            f"""
        SELECT id, file_path, rom_id, emulator
        FROM saves
        WHERE {like_clause}
    """
        )
    ).fetchall()  # nosec B608

    for row in results:
        save_id = row.id
        old_path = row.file_path
        rom_id = row.rom_id
        emulator = row.emulator

        if not emulator or not rom_id or not old_path:
            continue  # Skip incomplete records

        # Extract user_id and platform from old path
        parts = old_path.split("/")
        try:
            user_id = parts[1]
            platform = parts[3]
        except IndexError:
            log.info(f"Skipping malformed path: {old_path}")
            continue

        new_path = f"users/{user_id}/saves/{platform}/{rom_id}/{emulator}"

        old_abs = os.path.join(ASSETS_BASE_PATH, *old_path.split("/"))
        new_abs = os.path.join(ASSETS_BASE_PATH, *new_path.split("/"))

        try:
            os.makedirs(os.path.dirname(new_abs), exist_ok=True)
            if os.path.exists(old_abs):
                os.rename(old_abs, new_abs)
                log.info(f"Moved: {old_abs} -> {new_abs}")
            else:
                log.info(f"Old path does not exist: {old_abs}")
        except Exception as e:
            log.info(f"Error moving {old_abs} to {new_abs}: {e}")
            continue

        # Update DB with new relative path
        conn.execute(
            text(
                """
            UPDATE saves
            SET file_path = :new_path
            WHERE id = :save_id
        """
            ),
            {"new_path": new_path, "save_id": save_id},
        )


def downgrade() -> None:
    # Optional: implement reverse if structure of old paths is known
    pass
