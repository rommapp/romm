"""empty message

Revision ID: 0034_virtual_collections_db_view
Revises: 0033_rom_file_and_hashes
Create Date: 2024-08-08 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0034_virtual_collections_db_view"
down_revision = "0033_rom_file_and_hashes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if is_postgresql(connection):
        connection.execute(
            sa.text(
                """
                CREATE OR REPLACE VIEW virtual_collections AS
                WITH genres_collection AS (
                    SELECT 
                        r.id as rom_id,
                        jsonb_array_elements_text(to_jsonb(igdb_metadata ->> 'genres')) as collection_name,
                        'genre' as collection_type
                    FROM roms r
                    WHERE igdb_metadata->>'genres' IS NOT NULL
                ),
                franchises_collection AS (
                    SELECT 
                        r.id as rom_id,
                        jsonb_array_elements_text(to_jsonb(igdb_metadata->>'franchises')) as collection_name,
                        'franchise' as collection_type
                    FROM roms r
                    WHERE igdb_metadata->>'franchises' IS NOT NULL
                ),
                collection_collection AS (
                    SELECT 
                        r.id as rom_id,
                        jsonb_array_elements_text(to_jsonb(igdb_metadata->>'collections')) as collection_name,
                        'collection' as collection_type
                    FROM roms r
                    WHERE igdb_metadata->>'collections' IS NOT NULL
                ),
                modes_collection AS (
                    SELECT 
                        r.id as rom_id,
                        jsonb_array_elements_text(to_jsonb(igdb_metadata->>'game_modes')) as collection_name,
                        'mode' as collection_type
                    FROM roms r
                    WHERE igdb_metadata->>'game_modes' IS NOT NULL
                ),
                companies_collection AS (
                    SELECT 
                        r.id as rom_id,
                        jsonb_array_elements_text(to_jsonb(igdb_metadata->>'companies')) as collection_name,
                        'company' as collection_type
                    FROM roms r
                    WHERE igdb_metadata->>'companies' IS NOT NULL
                )
                SELECT 
                collection_name,
                collection_type,
                array_agg(DISTINCT rom_id) as roms
                FROM (
                    SELECT * FROM genres_collection
                    UNION ALL
                    SELECT * FROM franchises_collection
                    UNION ALL
                    SELECT * FROM collection_collection
                    UNION ALL
                    SELECT * FROM modes_collection
                    UNION ALL
                    SELECT * FROM companies_collection
                ) combined
                GROUP BY collection_type, collection_name
                HAVING COUNT(DISTINCT rom_id) > 1
                ORDER BY collection_type, collection_name;
                """  # nosec B608
            ),
        )
    else:
        connection.execute(
            sa.text(
                """
                CREATE OR REPLACE VIEW virtual_collections AS 
                WITH genres AS (
                    SELECT
                        r.id as rom_id,
                        CONCAT(j.genre) as collection_name,
                        'genre' as collection_type
                    FROM
                        roms r
                        CROSS JOIN JSON_TABLE(
                            JSON_EXTRACT(igdb_metadata, '$.genres'),
                            '$[*]' COLUMNS (genre VARCHAR(255) PATH '$')
                        ) j
                    WHERE
                        JSON_EXTRACT(igdb_metadata, '$.genres') IS NOT NULL
                ),
                franchises AS (
                    SELECT
                        r.id as rom_id,
                        CONCAT(j.franchise) as collection_name,
                        'franchise' as collection_type
                    FROM
                        roms r
                        CROSS JOIN JSON_TABLE(
                            JSON_EXTRACT(igdb_metadata, '$.franchises'),
                            '$[*]' COLUMNS (franchise VARCHAR(255) PATH '$')
                        ) j
                    WHERE
                        JSON_EXTRACT(igdb_metadata, '$.franchises') IS NOT NULL
                ),
                collections AS (
                    SELECT
                        r.id as rom_id,
                        CONCAT(j.collection) as collection_name,
                        'collection' as collection_type
                    FROM
                        roms r
                        CROSS JOIN JSON_TABLE(
                            JSON_EXTRACT(igdb_metadata, '$.collections'),
                            '$[*]' COLUMNS (collection VARCHAR(255) PATH '$')
                        ) j
                    WHERE
                        JSON_EXTRACT(igdb_metadata, '$.collections') IS NOT NULL
                ),
                modes AS (
                    SELECT
                        r.id as rom_id,
                        CONCAT(j.mode) as collection_name,
                        'mode' as collection_type
                    FROM
                        roms r
                        CROSS JOIN JSON_TABLE(
                            JSON_EXTRACT(igdb_metadata, '$.game_modes'),
                            '$[*]' COLUMNS (mode VARCHAR(255) PATH '$')
                        ) j
                    WHERE
                        JSON_EXTRACT(igdb_metadata, '$.game_modes') IS NOT NULL
                ),
                companies AS (
                    SELECT
                        r.id as rom_id,
                        CONCAT(j.company) as collection_name,
                        'company' as collection_type
                    FROM
                        roms r
                        CROSS JOIN JSON_TABLE(
                            JSON_EXTRACT(igdb_metadata, '$.companies'),
                            '$[*]' COLUMNS (company VARCHAR(255) PATH '$')
                        ) j
                    WHERE
                        JSON_EXTRACT(igdb_metadata, '$.companies') IS NOT NULL
                )
                SELECT
                    collection_name,
                    collection_type,
                    GROUP_CONCAT(DISTINCT rom_id) as roms
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
                HAVING COUNT(DISTINCT rom_id) > 1
                ORDER BY collection_type, collection_name;
                """
            ),
        )


def downgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            DROP VIEW virtual_collections;
            """
        ),
    )
