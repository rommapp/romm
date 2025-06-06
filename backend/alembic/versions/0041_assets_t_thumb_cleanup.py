"""empty message

Revision ID: 0041_assets_t_thumb_cleanup
Revises: 0040_migrate_assets_paths
Create Date: 2025-06-06 16:22:08.361524

"""

import json

from alembic import op
from sqlalchemy.sql import text
from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0041_assets_t_thumb_cleanup"
down_revision = "0040_migrate_assets_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        text(
            """
            UPDATE roms 
            SET url_cover = replace(url_cover, 't_thumb', 't_1080p')
            WHERE url_cover LIKE '%t_thumb%'
            """
        )
    )

    if is_postgresql(conn):
        conn.execute(
            text(
                """
                UPDATE roms 
                SET url_screenshots = (
                    SELECT jsonb_agg(
                        to_jsonb(replace(value, 't_thumb', 't_720p'))
                    )
                    FROM jsonb_array_elements_text(url_screenshots) AS value
                )
                WHERE url_screenshots IS NOT NULL
                AND url_screenshots::text LIKE '%t_thumb%';
                """
            )
        )
    else:
        result = conn.execute(
            text(
                """
                SELECT id, url_screenshots
                FROM roms
                WHERE JSON_SEARCH(url_screenshots, 'one', '%t_thumb%') IS NOT NULL
                """
            )
        )

        for row in result:
            row_id, screenshots_json = row
            if screenshots_json:
                try:
                    screenshots = json.loads(screenshots_json)
                    if isinstance(screenshots, list):
                        updated_screenshots = [
                            (
                                url.replace("t_thumb", "t_720p")
                                if isinstance(url, str)
                                else url
                            )
                            for url in screenshots
                        ]
                        conn.execute(
                            text(
                                """
                                UPDATE roms
                                SET url_screenshots = :screenshots
                                WHERE id = :id
                                """
                            ),
                            {
                                "screenshots": json.dumps(updated_screenshots),
                                "id": row_id,
                            },
                        )
                except json.JSONDecodeError:
                    continue


def downgrade() -> None:
    pass
