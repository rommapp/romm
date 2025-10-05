"""empty message

Revision ID: 0037_virtual_rom_columns
Revises: 0036_screenscraper_platforms_id
Create Date: 2025-03-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0037_virtual_rom_columns"
down_revision = "0036_screenscraper_platforms_id"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if is_postgresql(connection):
        connection.execute(
            sa.text(
                """
                CREATE OR REPLACE VIEW roms_metadata AS
                SELECT
                    r.id AS rom_id,
                    NOW() AS created_at,
                    NOW() AS updated_at,
                    COALESCE(
                        (r.igdb_metadata -> 'genres'),
                        (r.moby_metadata -> 'genres'),
                        (r.ss_metadata -> 'genres'),
                        '[]'::jsonb
                    ) AS genres,

                    CASE
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'franchises' THEN r.igdb_metadata -> 'franchises'
                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'franchises' THEN r.ss_metadata -> 'franchises'
                        ELSE '[]'::jsonb
                    END AS franchises,

                    CASE
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'collections' THEN r.igdb_metadata -> 'collections'
                        ELSE '[]'::jsonb
                    END AS collections,

                    CASE
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'companies' THEN r.igdb_metadata -> 'companies'
                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'companies' THEN r.ss_metadata -> 'companies'
                        ELSE '[]'::jsonb
                    END AS companies,

                    CASE
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'game_modes' THEN r.igdb_metadata -> 'game_modes'
                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'game_modes' THEN r.ss_metadata -> 'game_modes'
                        ELSE '[]'::jsonb
                    END AS game_modes,

                    COALESCE(
                        jsonb_path_query_array(
                            r.igdb_metadata,
                            '$.age_ratings[*].rating'
                        ),
                        '[]'::jsonb
                    ) AS age_ratings,

                    CASE
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'first_release_date' AND
                            r.igdb_metadata ->> 'first_release_date' NOT IN ('null', 'None', '') AND
                            r.igdb_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.igdb_metadata ->> 'first_release_date')::bigint * 1000

                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'first_release_date' AND
                            r.ss_metadata ->> 'first_release_date' NOT IN ('null', 'None', '') AND
                            r.ss_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.ss_metadata ->> 'first_release_date')::bigint * 1000

                        ELSE NULL
                    END AS first_release_date,

                    CASE
                        WHEN (igdb_rating IS NOT NULL OR moby_rating IS NOT NULL OR ss_rating IS NOT NULL) THEN
                            (COALESCE(igdb_rating, 0) + COALESCE(moby_rating, 0) + COALESCE(ss_rating, 0)) /
                            (CASE WHEN igdb_rating IS NOT NULL THEN 1 ELSE 0 END +
                            CASE WHEN moby_rating IS NOT NULL THEN 1 ELSE 0 END +
                            CASE WHEN ss_rating IS NOT NULL THEN 1 ELSE 0 END)
                        ELSE NULL
                    END AS average_rating
                FROM (
                    SELECT
                        r.id,
                        r.igdb_metadata,
                        r.moby_metadata,
                        r.ss_metadata,
                        CASE
                            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'total_rating' AND
                                r.igdb_metadata ->> 'total_rating' NOT IN ('null', 'None', '') AND
                                r.igdb_metadata ->> 'total_rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.igdb_metadata ->> 'total_rating')::float
                            ELSE NULL
                        END AS igdb_rating,
                        CASE
                            WHEN r.moby_metadata IS NOT NULL AND r.moby_metadata ? 'moby_score' AND
                                r.moby_metadata ->> 'moby_score' NOT IN ('null', 'None', '') AND
                                r.moby_metadata ->> 'moby_score' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.moby_metadata ->> 'moby_score')::float * 10
                            ELSE NULL
                        END AS moby_rating,
                        CASE
                            WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'ss_score' AND
                                r.ss_metadata ->> 'ss_score' NOT IN ('null', 'None', '') AND
                                r.ss_metadata ->> 'ss_score' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.ss_metadata ->> 'ss_score')::float
                            ELSE NULL
                        END AS ss_rating
                    FROM roms r
                ) AS r;
                """
            )
        )
    else:
        connection.execute(
            sa.text(
                """CREATE OR REPLACE VIEW roms_metadata AS
                    SELECT
                        r.id as rom_id,
                        NOW() AS created_at,
                        NOW() AS updated_at,
                        COALESCE(
                            JSON_EXTRACT(r.igdb_metadata, '$.genres'),
                            JSON_EXTRACT(r.moby_metadata, '$.genres'),
                            JSON_EXTRACT(r.ss_metadata, '$.genres'),
                            JSON_ARRAY()
                        ) AS genres,

                        CASE
                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.franchises') THEN JSON_EXTRACT(r.igdb_metadata, '$.franchises')
                            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.franchises') THEN JSON_EXTRACT(r.ss_metadata, '$.franchises')
                            ELSE JSON_ARRAY()
                        END AS franchises,

                        CASE
                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.collections') THEN JSON_EXTRACT(r.igdb_metadata, '$.collections')
                            ELSE JSON_ARRAY()
                        END AS collections,

                        CASE
                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.companies') THEN JSON_EXTRACT(r.igdb_metadata, '$.companies')
                            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.companies') THEN JSON_EXTRACT(r.ss_metadata, '$.companies')
                            ELSE JSON_ARRAY()
                        END AS companies,

                        CASE
                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.game_modes') THEN JSON_EXTRACT(r.igdb_metadata, '$.game_modes')
                            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.game_modes') THEN JSON_EXTRACT(r.ss_metadata, '$.game_modes')
                            ELSE JSON_ARRAY()
                        END AS game_modes,

                        CASE
                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.age_ratings')
                                AND JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings')) > 0
                            THEN
                                JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')
                            ELSE
                                JSON_ARRAY()
                        END AS age_ratings,

                        CASE
                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.first_release_date') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) NOT IN ('null', 'None', '') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date') AS SIGNED) * 1000

                            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.first_release_date') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) NOT IN ('null', 'None', '') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_EXTRACT(r.ss_metadata, '$.first_release_date') AS SIGNED) * 1000

                            ELSE NULL
                        END AS first_release_date,

                        CASE
                            WHEN (igdb_rating IS NOT NULL OR moby_rating IS NOT NULL OR ss_rating IS NOT NULL) THEN
                                (COALESCE(igdb_rating, 0) + COALESCE(moby_rating, 0) + COALESCE(ss_rating, 0)) /
                                (CASE WHEN igdb_rating IS NOT NULL THEN 1 ELSE 0 END +
                                CASE WHEN moby_rating IS NOT NULL THEN 1 ELSE 0 END +
                                CASE WHEN ss_rating IS NOT NULL THEN 1 ELSE 0 END)
                            ELSE NULL
                        END AS average_rating

                    FROM (
                        SELECT
                            id,
                            igdb_metadata,
                            moby_metadata,
                            ss_metadata,
                            CASE
                                WHEN JSON_CONTAINS_PATH(igdb_metadata, 'one', '$.total_rating') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) NOT IN ('null', 'None', '') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(igdb_metadata, '$.total_rating') AS DECIMAL(10,2))
                                ELSE NULL
                            END AS igdb_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(moby_metadata, 'one', '$.moby_score') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) NOT IN ('null', 'None', '') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(moby_metadata, '$.moby_score') AS DECIMAL(10,2)) * 10
                                ELSE NULL
                            END AS moby_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(ss_metadata, 'one', '$.ss_score') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) NOT IN ('null', 'None', '') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(ss_metadata, '$.ss_score') AS DECIMAL(10,2)) * 10
                                ELSE NULL
                            END AS ss_rating
                        FROM roms
                    ) AS r;
                """
            )
        )


def downgrade():
    op.execute("DROP VIEW IF EXISTS roms_metadata")
