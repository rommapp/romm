"""empty message

Revision ID: 0045_roms_metadata_update
Revises: 0044_hasheous_id
Create Date: 2025-03-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0045_roms_metadata_update"
down_revision = "0044_hasheous_id"
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
                        (r.launchbox_metadata -> 'genres'),
                        (r.ra_metadata -> 'genres'),
                        '[]'::jsonb
                    ) AS genres,

                    COALESCE(
                        (r.igdb_metadata -> 'franchises'),
                        (r.ss_metadata -> 'franchises'),
                        '[]'::jsonb
                    ) AS franchises,

                    COALESCE(
                        (r.igdb_metadata -> 'collections'),
                        '[]'::jsonb
                    ) AS collections,

                    COALESCE(
                        (r.igdb_metadata -> 'companies'),
                        (r.ss_metadata -> 'companies'),
                        (r.ra_metadata -> 'companies'),
                        (r.launchbox_metadata -> 'companies'),
                        '[]'::jsonb
                    ) AS companies,

                    COALESCE(
                        (r.igdb_metadata -> 'game_modes'),
                        (r.ss_metadata -> 'game_modes'),
                        '[]'::jsonb
                    ) AS game_modes,

                    COALESCE(
                        CASE
                            WHEN r.igdb_metadata IS NOT NULL
                                AND r.igdb_metadata ? 'age_ratings'
                                AND jsonb_array_length(r.igdb_metadata -> 'age_ratings') > 0
                            THEN
                                jsonb_path_query_array(r.igdb_metadata, '$.age_ratings[*].rating')
                            ELSE
                                '[]'::jsonb
                        END,
                        CASE
                            WHEN r.launchbox_metadata IS NOT NULL
                                AND r.launchbox_metadata ? 'esrb'
                                AND r.launchbox_metadata ->> 'esrb' IS NOT NULL
                                AND r.launchbox_metadata ->> 'esrb' != ''
                            THEN
                                jsonb_build_array(r.launchbox_metadata ->> 'esrb')
                            ELSE
                                '[]'::jsonb
                        END,
                        '[]'::jsonb
                    ) AS age_ratings,

                    CASE
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'first_release_date' AND
                            r.igdb_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.igdb_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.igdb_metadata ->> 'first_release_date')::bigint * 1000

                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'first_release_date' AND
                            r.ss_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.ss_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.ss_metadata ->> 'first_release_date')::bigint * 1000

                        WHEN r.ra_metadata IS NOT NULL AND r.ra_metadata ? 'first_release_date' AND
                            r.ra_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.ra_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.ra_metadata ->> 'first_release_date')::bigint * 1000

                        WHEN r.launchbox_metadata IS NOT NULL AND r.launchbox_metadata ? 'first_release_date' AND
                            r.launchbox_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.launchbox_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.launchbox_metadata ->> 'first_release_date')::bigint * 1000

                        ELSE NULL
                    END AS first_release_date,

                    CASE
                        WHEN (igdb_rating IS NOT NULL OR moby_rating IS NOT NULL OR ss_rating IS NOT NULL OR launchbox_rating IS NOT NULL) THEN
                            (COALESCE(igdb_rating, 0) + COALESCE(moby_rating, 0) + COALESCE(ss_rating, 0) + COALESCE(launchbox_rating, 0)) /
                            (CASE WHEN igdb_rating IS NOT NULL THEN 1 ELSE 0 END +
                            CASE WHEN moby_rating IS NOT NULL THEN 1 ELSE 0 END +
                            CASE WHEN ss_rating IS NOT NULL THEN 1 ELSE 0 END +
                            CASE WHEN launchbox_rating IS NOT NULL THEN 1 ELSE 0 END)
                        ELSE NULL
                    END AS average_rating
                FROM (
                    SELECT
                        r.id,
                        r.igdb_metadata,
                        r.moby_metadata,
                        r.ss_metadata,
                        r.ra_metadata,
                        r.launchbox_metadata,
                        CASE
                            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'total_rating' AND
                                r.igdb_metadata ->> 'total_rating' NOT IN ('null', 'None', '0', '0.0') AND
                                r.igdb_metadata ->> 'total_rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.igdb_metadata ->> 'total_rating')::float
                            ELSE NULL
                        END AS igdb_rating,
                        CASE
                            WHEN r.moby_metadata IS NOT NULL AND r.moby_metadata ? 'moby_score' AND
                                r.moby_metadata ->> 'moby_score' NOT IN ('null', 'None', '0', '0.0') AND
                                r.moby_metadata ->> 'moby_score' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.moby_metadata ->> 'moby_score')::float * 10
                            ELSE NULL
                        END AS moby_rating,
                        CASE
                            WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'ss_score' AND
                                r.ss_metadata ->> 'ss_score' NOT IN ('null', 'None', '0', '0.0') AND
                                r.ss_metadata ->> 'ss_score' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.ss_metadata ->> 'ss_score')::float * 10
                            ELSE NULL
                        END AS ss_rating,
                        CASE
                            WHEN r.launchbox_metadata IS NOT NULL AND r.launchbox_metadata ? 'community_rating' AND
                                r.launchbox_metadata ->> 'community_rating' NOT IN ('null', 'None', '0', '0.0') AND
                                r.launchbox_metadata ->> 'community_rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.launchbox_metadata ->> 'community_rating')::float * 20
                            ELSE NULL
                        END AS launchbox_rating
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
                            JSON_EXTRACT(r.launchbox_metadata, '$.genres'),
                            JSON_EXTRACT(r.ra_metadata, '$.genres'),
                            JSON_ARRAY()
                        ) AS genres,

                        COALESCE(
                            JSON_EXTRACT(r.igdb_metadata, '$.franchises'),
                            JSON_EXTRACT(r.ss_metadata, '$.franchises'),
                            JSON_ARRAY()
                        ) AS franchises,

                        COALESCE(
                            JSON_EXTRACT(r.igdb_metadata, '$.collections'),
                            JSON_ARRAY()
                        ) AS collections,

                        COALESCE(
                            JSON_EXTRACT(r.igdb_metadata, '$.companies'),
                            JSON_EXTRACT(r.ss_metadata, '$.companies'),
                            JSON_EXTRACT(r.ra_metadata, '$.companies'),
                            JSON_EXTRACT(r.launchbox_metadata, '$.companies'),
                            JSON_ARRAY()
                        ) AS companies,

                        COALESCE(
                            JSON_EXTRACT(r.igdb_metadata, '$.game_modes'),
                            JSON_EXTRACT(r.ss_metadata, '$.game_modes'),
                            JSON_ARRAY()
                        ) AS game_modes,

                        COALESCE(
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.age_ratings')
                                    AND JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings')) > 0
                                THEN
                                    JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')
                                ELSE
                                    JSON_ARRAY()
                            END,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.esrb')
                                    AND JSON_EXTRACT(r.launchbox_metadata, '$.esrb') IS NOT NULL
                                    AND JSON_EXTRACT(r.launchbox_metadata, '$.esrb') != ''
                                THEN
                                    JSON_ARRAY(JSON_EXTRACT(r.launchbox_metadata, '$.esrb'))
                                ELSE
                                    JSON_ARRAY()
                            END,
                            JSON_ARRAY()
                        ) AS age_ratings,

                        CASE
                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.first_release_date') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date') AS SIGNED) * 1000

                            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.first_release_date') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_EXTRACT(r.ss_metadata, '$.first_release_date') AS SIGNED) * 1000

                            WHEN JSON_CONTAINS_PATH(r.ra_metadata, 'one', '$.first_release_date') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.ra_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.ra_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_EXTRACT(r.ra_metadata, '$.first_release_date') AS SIGNED) * 1000

                            WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.first_release_date') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_EXTRACT(r.launchbox_metadata, '$.first_release_date') AS SIGNED) * 1000

                            ELSE NULL
                        END AS first_release_date,

                        CASE
                            WHEN (igdb_rating IS NOT NULL OR moby_rating IS NOT NULL OR ss_rating IS NOT NULL OR launchbox_rating IS NOT NULL) THEN
                                (COALESCE(igdb_rating, 0) + COALESCE(moby_rating, 0) + COALESCE(ss_rating, 0) + COALESCE(launchbox_rating, 0)) /
                                (CASE WHEN igdb_rating IS NOT NULL THEN 1 ELSE 0 END +
                                CASE WHEN moby_rating IS NOT NULL THEN 1 ELSE 0 END +
                                CASE WHEN ss_rating IS NOT NULL THEN 1 ELSE 0 END +
                                CASE WHEN launchbox_rating IS NOT NULL THEN 1 ELSE 0 END)
                            ELSE NULL
                        END AS average_rating
                    FROM (
                        SELECT
                            id,
                            igdb_metadata,
                            moby_metadata,
                            ss_metadata,
                            ra_metadata,
                            launchbox_metadata,
                            CASE
                                WHEN JSON_CONTAINS_PATH(igdb_metadata, 'one', '$.total_rating') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) NOT IN ('null', 'None', '0', '0.0') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(igdb_metadata, '$.total_rating') AS DECIMAL(10,2))
                                ELSE NULL
                            END AS igdb_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(moby_metadata, 'one', '$.moby_score') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) NOT IN ('null', 'None', '0', '0.0') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(moby_metadata, '$.moby_score') AS DECIMAL(10,2)) * 10
                                ELSE NULL
                            END AS moby_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(ss_metadata, 'one', '$.ss_score') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) NOT IN ('null', 'None', '0', '0.0') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(ss_metadata, '$.ss_score') AS DECIMAL(10,2)) * 10
                                ELSE NULL
                            END AS ss_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(launchbox_metadata, 'one', '$.community_rating') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(launchbox_metadata, '$.community_rating')) NOT IN ('null', 'None', '0', '0.0') AND
                                    JSON_UNQUOTE(JSON_EXTRACT(launchbox_metadata, '$.community_rating')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(launchbox_metadata, '$.community_rating') AS DECIMAL(10,2)) * 20
                                ELSE NULL
                            END AS launchbox_rating
                        FROM roms
                    ) AS r;
                """
            )
        )


def downgrade():
    op.execute("DROP VIEW IF EXISTS roms_metadata")
