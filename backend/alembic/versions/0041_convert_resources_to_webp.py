"""convert resource paths to webp and update db

Revision ID: 0041_convert_resources_to_webp
Revises: 0040_migrate_assets_paths
Create Date: 2025-05-29 00:00:00.000000
"""

import json
import os

from alembic import op
from config import RESOURCES_BASE_PATH
from logger.logger import log
from sqlalchemy.sql import text

revision = "0041_convert_resources_to_webp"
down_revision = "0040_migrate_assets_paths"
branch_labels = None
depends_on = None


def convert_to_webp(abs_path):
    from PIL import Image, UnidentifiedImageError

    base, ext = os.path.splitext(abs_path)
    if ext.lower() == ".webp":
        return abs_path  # Already webp

    webp_path = base + ".webp"
    if os.path.exists(webp_path):
        return webp_path  # Already converted

    try:
        with Image.open(abs_path) as img:
            img.save(webp_path, format="WEBP", quality=90, method=6)
        os.remove(abs_path)
        log.info(f"Converted {abs_path} to {webp_path}")
        return webp_path
    except UnidentifiedImageError:
        log.warning(f"Not an image: {abs_path}")
        return abs_path
    except Exception as exc:
        log.error(f"Failed to convert {abs_path}: {exc}")
        return abs_path


def rel_to_webp(rel_path):
    base, ext = os.path.splitext(rel_path)
    if ext.lower() == ".webp":
        return rel_path
    return base + ".webp"


def upgrade():
    conn = op.get_bind()

    # --- ROMS TABLE ---
    results = conn.execute(
        text("SELECT id, path_cover_s, path_cover_l, path_screenshots FROM roms")
    ).fetchall()

    for row in results:
        updates = {}
        # Cover small
        if row.path_cover_s:
            abs_path = os.path.join(RESOURCES_BASE_PATH, row.path_cover_s)
            new_abs = convert_to_webp(abs_path)
            new_rel = rel_to_webp(row.path_cover_s)
            if new_abs != abs_path:
                updates["path_cover_s"] = new_rel

        # Cover large
        if row.path_cover_l:
            abs_path = os.path.join(RESOURCES_BASE_PATH, row.path_cover_l)
            new_abs = convert_to_webp(abs_path)
            new_rel = rel_to_webp(row.path_cover_l)
            if new_abs != abs_path:
                updates["path_cover_l"] = new_rel

        # Screenshots (JSON string)
        if row.path_screenshots:
            try:
                screenshots = json.loads(row.path_screenshots)
            except Exception:
                log.error(f"Invalid JSON in path_screenshots for rom id {row.id}")
                screenshots = []
            new_screens = []
            changed = False
            for s in screenshots:
                abs_path = os.path.join(RESOURCES_BASE_PATH, s)
                new_abs = convert_to_webp(abs_path)
                new_rel = rel_to_webp(s)
                new_screens.append(new_rel)
                if new_abs != abs_path:
                    changed = True
            if changed:
                updates["path_screenshots"] = json.dumps(new_screens)

        # Update DB if needed
        if updates:
            set_clause = ", ".join([f"{k} = :{k}" for k in updates])
            params = {**updates, "id": row.id}
            conn.execute(
                text(f"UPDATE roms SET {set_clause} WHERE id = :id"),
                params,
            )
            log.info(f"Updated rom id {row.id}: {updates}")

    # --- COLLECTIONS TABLE ---
    results = conn.execute(
        text("SELECT id, path_cover_s, path_cover_l FROM collections")
    ).fetchall()

    for row in results:
        updates = {}
        if row.path_cover_s:
            abs_path = os.path.join(RESOURCES_BASE_PATH, row.path_cover_s)
            new_abs = convert_to_webp(abs_path)
            new_rel = rel_to_webp(row.path_cover_s)
            if new_abs != abs_path:
                updates["path_cover_s"] = new_rel
        if row.path_cover_l:
            abs_path = os.path.join(RESOURCES_BASE_PATH, row.path_cover_l)
            new_abs = convert_to_webp(abs_path)
            new_rel = rel_to_webp(row.path_cover_l)
            if new_abs != abs_path:
                updates["path_cover_l"] = new_rel
        if updates:
            set_clause = ", ".join([f"{k} = :{k}" for k in updates])
            params = {**updates, "id": row.id}
            conn.execute(
                text(f"UPDATE collections SET {set_clause} WHERE id = :id"),
                params,
            )
            log.info(f"Updated collection id {row.id}: {updates}")


def downgrade():
    # Not implemented
    pass
