"""Pin explicit collation in virtual_collections view (MariaDB 11.6+ compatibility)

On MariaDB 11.6+ the default ``character_set_collations`` maps utf8mb4
expressions to ``utf8mb4_uca1400_ai_ci``, while the view's string literals and
JSON_TABLE columns resolve under the connection collation the view was created
with (commonly ``utf8mb4_general_ci``). Mixing the two in comparisons raises
``Illegal mix of collations (...) for operation '='`` and every
``/api/collections/virtual`` request fails with HTTP 500 (issue #3758).

Recreate the view with an explicit ``COLLATE utf8mb4_general_ci`` on each
string output column: an explicit collation has the strongest coercibility, so
comparisons resolve deterministically regardless of the server's
``character_set_collations`` setting. No behavior change on PostgreSQL.

Revision ID: 0096_fix_virtual_collections
Revises: 0095_virtual_collections_source
Create Date: 2026-07-15 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0096_fix_virtual_collections"
down_revision = "0095_virtual_collections_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    if is_postgresql(connection):
        # PostgreSQL is unaffected; keep the view from 0095 as-is.
        return

    connection.execute(
        sa.text("""
                CREATE OR REPLACE VIEW virtual_collections AS
                WITH base AS (
                    SELECT
                        r.id as rom_id,
                        r.path_cover_s as path_cover_s,
                        r.path_cover_l as path_cover_l,
                        rm.genres as genres,
                        rm.franchises as franchises,
                        rm.collections as collections,
                        rm.game_modes as game_modes,
                        rm.companies as companies
                    FROM
                        roms r
                        JOIN roms_metadata rm ON rm.rom_id = r.id
                ),
                genres AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.genre) COLLATE utf8mb4_general_ci as collection_name,
                        'genre' COLLATE utf8mb4_general_ci as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.genres,
                            '$[*]' COLUMNS (genre VARCHAR(255) PATH '$')
                        ) j
                ),
                franchises AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.franchise) COLLATE utf8mb4_general_ci as collection_name,
                        'franchise' COLLATE utf8mb4_general_ci as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.franchises,
                            '$[*]' COLUMNS (franchise VARCHAR(255) PATH '$')
                        ) j
                ),
                collections AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.collection) COLLATE utf8mb4_general_ci as collection_name,
                        'collection' COLLATE utf8mb4_general_ci as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.collections,
                            '$[*]' COLUMNS (collection VARCHAR(255) PATH '$')
                        ) j
                ),
                modes AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.mode) COLLATE utf8mb4_general_ci as collection_name,
                        'mode' COLLATE utf8mb4_general_ci as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.game_modes,
                            '$[*]' COLUMNS (mode VARCHAR(255) PATH '$')
                        ) j
                ),
                companies AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.company) COLLATE utf8mb4_general_ci as collection_name,
                        'company' COLLATE utf8mb4_general_ci as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.companies,
                            '$[*]' COLUMNS (company VARCHAR(255) PATH '$')
                        ) j
                )
                SELECT
                    collection_name as name,
                    collection_type as type,
                    CONCAT('Autogenerated ', collection_name, ' collection') COLLATE utf8mb4_general_ci AS description,
                    NOW() AS created_at,
                    NOW() AS updated_at,
                    JSON_ARRAYAGG(rom_id) as rom_ids,
                    JSON_ARRAYAGG(path_cover_s) as path_covers_s,
                    JSON_ARRAYAGG(path_cover_l) as path_covers_l
                FROM
                (
                    SELECT * FROM genres
                    UNION ALL
                    SELECT * FROM franchises
                    UNION ALL
                    SELECT * FROM collections
                    UNION ALL
                    SELECT * FROM modes
                    UNION ALL
                    SELECT * FROM companies
                ) combined
                GROUP BY collection_type, collection_name
                HAVING COUNT(DISTINCT rom_id) > 2
                ORDER BY collection_type, collection_name;
                """),
    )


def downgrade() -> None:
    connection = op.get_bind()

    if is_postgresql(connection):
        return

    connection.execute(
        sa.text("""
                CREATE OR REPLACE VIEW virtual_collections AS
                WITH base AS (
                    SELECT
                        r.id as rom_id,
                        r.path_cover_s as path_cover_s,
                        r.path_cover_l as path_cover_l,
                        rm.genres as genres,
                        rm.franchises as franchises,
                        rm.collections as collections,
                        rm.game_modes as game_modes,
                        rm.companies as companies
                    FROM
                        roms r
                        JOIN roms_metadata rm ON rm.rom_id = r.id
                ),
                genres AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.genre) as collection_name,
                        'genre' as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.genres,
                            '$[*]' COLUMNS (genre VARCHAR(255) PATH '$')
                        ) j
                ),
                franchises AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.franchise) as collection_name,
                        'franchise' as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.franchises,
                            '$[*]' COLUMNS (franchise VARCHAR(255) PATH '$')
                        ) j
                ),
                collections AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.collection) as collection_name,
                        'collection' as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.collections,
                            '$[*]' COLUMNS (collection VARCHAR(255) PATH '$')
                        ) j
                ),
                modes AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.mode) as collection_name,
                        'mode' as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.game_modes,
                            '$[*]' COLUMNS (mode VARCHAR(255) PATH '$')
                        ) j
                ),
                companies AS (
                    SELECT
                        base.rom_id as rom_id,
                        base.path_cover_s as path_cover_s,
                        base.path_cover_l as path_cover_l,
                        CONCAT(j.company) as collection_name,
                        'company' as collection_type
                    FROM
                        base
                        CROSS JOIN JSON_TABLE(
                            base.companies,
                            '$[*]' COLUMNS (company VARCHAR(255) PATH '$')
                        ) j
                )
                SELECT
                    collection_name as name,
                    collection_type as type,
                    CONCAT('Autogenerated ', collection_name, ' collection') AS description,
                    NOW() AS created_at,
                    NOW() AS updated_at,
                    JSON_ARRAYAGG(rom_id) as rom_ids,
                    JSON_ARRAYAGG(path_cover_s) as path_covers_s,
                    JSON_ARRAYAGG(path_cover_l) as path_covers_l
                FROM
                (
                    SELECT * FROM genres
                    UNION ALL
                    SELECT * FROM franchises
                    UNION ALL
                    SELECT * FROM collections
                    UNION ALL
                    SELECT * FROM modes
                    UNION ALL
                    SELECT * FROM companies
                ) combined
                GROUP BY collection_type, collection_name
                HAVING COUNT(DISTINCT rom_id) > 2
                ORDER BY collection_type, collection_name;
                """),
    )
