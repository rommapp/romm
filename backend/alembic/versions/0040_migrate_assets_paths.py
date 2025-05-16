"""migrate asset file paths to include rom_id

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

    # Table configuration: whether each table has an emulator column
    tables_with_emulator_column = {
        "saves": True,
        "states": True,
        "screenshots": False,
    }

    for table, has_emulator in tables_with_emulator_column.items():
        log.info(f"Processing table: {table}")

        # Database-specific LIKE clause
        like_clause = (
            "file_path NOT LIKE '%%/' || rom_id::text || '/%%'"
            if is_postgresql(conn)
            else "file_path NOT LIKE CONCAT('%/', rom_id, '/%')"
        )

        # Build query based on whether emulator exists
        select_cols = "id, file_path, rom_id" + (", emulator" if has_emulator else "")
        results = conn.execute(
            text(
                f"""
                SELECT {select_cols}
                FROM {table}
                WHERE {like_clause}
            """  # nosec B608
            )
        ).fetchall()

        for row in results:
            item_id = row.id
            old_path = row.file_path
            rom_id = row.rom_id
            emulator = row.emulator if has_emulator else None

            if not old_path or not rom_id:
                continue  # Skip incomplete records

            parts = old_path.split("/")
            try:
                user_id = parts[1]
                platform = parts[3]
            except IndexError:
                log.info(f"[{table}] Skipping malformed path: {old_path}")
                continue

            # Always include rom_id in the path
            path_parts = ["users", user_id, table, platform, str(rom_id)]
            if emulator:
                path_parts.append(emulator)
            new_path = "/".join(path_parts)

            old_abs = os.path.join(ASSETS_BASE_PATH, *old_path.split("/"))
            new_abs = os.path.join(ASSETS_BASE_PATH, *new_path.split("/"))

            try:
                os.makedirs(os.path.dirname(new_abs), exist_ok=True)

                if os.path.exists(old_abs):
                    if table == "screenshots" and os.path.isdir(old_abs):
                        # Move files individually to avoid moving directory into itself
                        for filename in os.listdir(old_abs):
                            src = os.path.join(old_abs, filename)
                            dst = os.path.join(new_abs, filename)
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            os.rename(src, dst)
                            log.info(f"[{table}] Moved file: {src} -> {dst}")
                    else:
                        os.rename(old_abs, new_abs)
                        log.info(f"[{table}] Moved: {old_abs} -> {new_abs}")
                else:
                    log.info(f"[{table}] Old path does not exist: {old_abs}")
            except Exception as e:
                log.error(f"[{table}] Error moving {old_abs} to {new_abs}: {e}")
                continue

            # Update DB
            conn.execute(
                text(
                    f"""
                    UPDATE {table}
                    SET file_path = :new_path
                    WHERE id = :item_id
                """  # nosec B608
                ),
                {"new_path": new_path, "item_id": item_id},
            )


def downgrade() -> None:
    # Optional: implement reverse logic if desired
    pass
