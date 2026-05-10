"""Prefer ScreenScraper genres over IGDB in roms_metadata

Revision ID: 0080_ss_genre_priority
Revises: 0079_add_rom_files_rom_id_index
Create Date: 2026-05-10 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0080_ss_genre_priority"
down_revision = "0079_add_rom_files_rom_id_index"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if is_postgresql(connection):
        connection.execute(
            sa.text("""
                CREATE OR REPLACE VIEW roms_metadata AS
                SELECT
                    r.id AS rom_id,
                    NOW() AS created_at,
                    NOW() AS updated_at,
                    COALESCE(
                        NULLIF(r.manual_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.ss_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.igdb_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.moby_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.launchbox_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.ra_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.flashpoint_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.gamelist_metadata -> 'genres', '[]'::jsonb),
                        '[]'::jsonb
                    ) AS genres,

                    COALESCE(
                        NULLIF(r.manual_metadata -> 'franchises', '[]'::jsonb),
                        NULLIF(r.igdb_metadata -> 'franchises', '[]'::jsonb),
                        NULLIF(r.ss_metadata -> 'franchises', '[]'::jsonb),
                        NULLIF(r.flashpoint_metadata -> 'franchises', '[]'::jsonb),
                        NULLIF(r.gamelist_metadata -> 'franchises', '[]'::jsonb),
                        '[]'::jsonb
                    ) AS franchises,

                    COALESCE(
                        (r.igdb_metadata -> 'collections'),
                        '[]'::jsonb
                    ) AS collections,

                    COALESCE(
                        NULLIF(r.manual_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.igdb_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.ss_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.ra_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.launchbox_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.flashpoint_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.gamelist_metadata -> 'companies', '[]'::jsonb),
                        '[]'::jsonb
                    ) AS companies,

                    COALESCE(
                        NULLIF(r.manual_metadata -> 'game_modes', '[]'::jsonb),
                        NULLIF(r.igdb_metadata -> 'game_modes', '[]'::jsonb),
                        NULLIF(r.ss_metadata -> 'game_modes', '[]'::jsonb),
                        NULLIF(r.flashpoint_metadata -> 'game_modes', '[]'::jsonb),
                        '[]'::jsonb
                    ) AS game_modes,

                    COALESCE(
                        (r.manual_metadata -> 'age_ratings'),
                        CASE
                            WHEN r.igdb_metadata IS NOT NULL
                                AND r.igdb_metadata ? 'age_ratings'
                                AND jsonb_array_length(r.igdb_metadata -> 'age_ratings') > 0
                            THEN
                                jsonb_path_query_array(r.igdb_metadata, '$.age_ratings[*].rating')
                            ELSE
                                NULL
                        END,
                        CASE
                            WHEN r.ss_metadata IS NOT NULL
                                AND r.ss_metadata ? 'age_ratings'
                                AND jsonb_array_length(r.ss_metadata -> 'age_ratings') > 0
                            THEN
                                jsonb_path_query_array(r.ss_metadata, '$.age_ratings[*].rating')
                            ELSE
                                NULL
                        END,
                        CASE
                            WHEN r.launchbox_metadata IS NOT NULL
                                AND r.launchbox_metadata ? 'esrb'
                                AND r.launchbox_metadata ->> 'esrb' IS NOT NULL
                                AND r.launchbox_metadata ->> 'esrb' != ''
                            THEN
                                jsonb_build_array(r.launchbox_metadata ->> 'esrb')
                            ELSE
                                NULL
                        END,
                        '[]'::jsonb
                    ) AS age_ratings,

                    CASE
                        WHEN r.manual_metadata IS NOT NULL AND r.manual_metadata ? 'first_release_date' AND
                            r.manual_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.manual_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.manual_metadata ->> 'first_release_date')::bigint

                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'first_release_date' AND
                            r.igdb_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.igdb_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.igdb_metadata ->> 'first_release_date')::bigint * 1000

                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'first_release_date' AND
                            r.ss_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.ss_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.ss_metadata ->> 'first_release_date')::bigint * 1000

                        WHEN r.launchbox_metadata IS NOT NULL AND r.launchbox_metadata ? 'release_date' AND
                            r.launchbox_metadata ->> 'release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.launchbox_metadata ->> 'release_date' ~ '^[0-9]+$'
                        THEN (r.launchbox_metadata ->> 'release_date')::bigint

                        WHEN r.flashpoint_metadata IS NOT NULL AND r.flashpoint_metadata ? 'release_date' AND
                            r.flashpoint_metadata ->> 'release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.flashpoint_metadata ->> 'release_date' ~ '^[0-9]+$'
                        THEN (r.flashpoint_metadata ->> 'release_date')::bigint

                        WHEN r.gamelist_metadata IS NOT NULL AND r.gamelist_metadata ? 'releasedate' AND
                            r.gamelist_metadata ->> 'releasedate' NOT IN ('null', 'None', '0', '0.0') AND
                            r.gamelist_metadata ->> 'releasedate' ~ '^[0-9]+$'
                        THEN (r.gamelist_metadata ->> 'releasedate')::bigint

                        ELSE NULL
                    END AS first_release_date,

                    COALESCE(
                        NULLIF(r.manual_metadata ->> 'player_count', ''),
                        NULLIF(r.igdb_metadata ->> 'player_count', ''),
                        NULLIF(r.ss_metadata ->> 'player_count', ''),
                        NULLIF(r.launchbox_metadata ->> 'max_players', ''),
                        '1'
                    ) AS player_count,

                    COALESCE(
                        NULLIF((
                            SELECT GREATEST(
                                COALESCE(igdb_rating, 0),
                                COALESCE(ss_rating, 0),
                                COALESCE(launchbox_rating, 0),
                                COALESCE(gamelist_rating, 0)
                            )
                        ), 0),
                        NULL
                    ) AS average_rating
                FROM (
                    SELECT
                        r.*,
                        CASE
                            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'total_rating' AND
                                r.igdb_metadata ->> 'total_rating' NOT IN ('null', 'None', '0', '0.0') AND
                                r.igdb_metadata ->> 'total_rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.igdb_metadata ->> 'total_rating')::float
                            ELSE NULL
                        END AS igdb_rating,
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
                        END AS launchbox_rating,
                        CASE
                            WHEN r.gamelist_metadata IS NOT NULL AND r.gamelist_metadata ? 'rating' AND
                                r.gamelist_metadata ->> 'rating' NOT IN ('null', 'None', '0', '0.0') AND
                                r.gamelist_metadata ->> 'rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.gamelist_metadata ->> 'rating')::float * 100
                            ELSE NULL
                        END AS gamelist_rating
                    FROM roms r
                ) AS r;
                """)
        )
    else:
        connection.execute(
            sa.text("""
                CREATE OR REPLACE VIEW roms_metadata AS
                    SELECT
                        r.id as rom_id,
                        NOW() AS created_at,
                        NOW() AS updated_at,
                        COALESCE(
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.moby_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.moby_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.launchbox_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.launchbox_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ra_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.ra_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.gamelist_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.gamelist_metadata, '$.genres') ELSE NULL END,
                            JSON_ARRAY()
                        ) AS genres,

                        COALESCE(
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.franchises') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.franchises') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.franchises') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.franchises') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.gamelist_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.gamelist_metadata, '$.franchises') ELSE NULL END,
                            JSON_ARRAY()
                        ) AS franchises,

                        COALESCE(
                            JSON_EXTRACT(r.igdb_metadata, '$.collections'),
                            JSON_ARRAY()
                        ) AS collections,

                        COALESCE(
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ra_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.ra_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.launchbox_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.launchbox_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.gamelist_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.gamelist_metadata, '$.companies') ELSE NULL END,
                            JSON_ARRAY()
                        ) AS companies,

                        COALESCE(
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.game_modes') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.game_modes') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.game_modes') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.game_modes') ELSE NULL END,
                            JSON_ARRAY()
                        ) AS game_modes,

                        COALESCE(
                            JSON_EXTRACT(r.manual_metadata, '$.age_ratings'),
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.age_ratings')
                                    AND JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings')) > 0
                                THEN
                                     IF(
                                        JSON_TYPE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                                        JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating'),
                                        JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')))
                                    )
                                ELSE
                                    NULL
                            END,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.age_ratings')
                                    AND JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.age_ratings')) > 0
                                THEN
                                     IF(
                                        JSON_TYPE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                                        JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating'),
                                        JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')))
                                    )
                                ELSE
                                    NULL
                            END,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.esrb')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.esrb')) IS NOT NULL
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.esrb')) != ''
                                THEN JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.esrb')))
                                ELSE NULL
                            END,
                            JSON_ARRAY()
                        ) AS age_ratings,

                        CASE
                            WHEN JSON_CONTAINS_PATH(r.manual_metadata, 'one', '$.first_release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) AS UNSIGNED)

                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.first_release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) AS UNSIGNED) * 1000

                            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.first_release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) AS UNSIGNED) * 1000

                            WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.release_date')) AS UNSIGNED)

                            WHEN JSON_CONTAINS_PATH(r.flashpoint_metadata, 'one', '$.release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.release_date')) AS UNSIGNED)

                            WHEN JSON_CONTAINS_PATH(r.gamelist_metadata, 'one', '$.releasedate')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.releasedate')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.releasedate')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.releasedate')) AS UNSIGNED)

                            ELSE NULL
                        END AS first_release_date,

                        COALESCE(
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.player_count')), ''),
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.player_count')), ''),
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.player_count')), ''),
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.max_players')), ''),
                            '1'
                        ) AS player_count,

                        COALESCE(
                            NULLIF(GREATEST(
                                COALESCE(igdb_rating, 0),
                                COALESCE(ss_rating, 0),
                                COALESCE(launchbox_rating, 0),
                                COALESCE(gamelist_rating, 0)
                            ), 0),
                            NULL
                        ) AS average_rating
                    FROM (
                        SELECT
                            r.*,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.total_rating')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.total_rating')) NOT IN ('null', 'None', '0', '0.0')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.total_rating')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.total_rating')) AS DECIMAL(10,2))
                                ELSE NULL
                            END AS igdb_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.ss_score')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.ss_score')) NOT IN ('null', 'None', '0', '0.0')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.ss_score')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.ss_score')) AS DECIMAL(10,2)) * 10
                                ELSE NULL
                            END AS ss_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.community_rating')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.community_rating')) NOT IN ('null', 'None', '0', '0.0')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.community_rating')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.community_rating')) AS DECIMAL(10,2)) * 20
                                ELSE NULL
                            END AS launchbox_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.gamelist_metadata, 'one', '$.rating')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.rating')) NOT IN ('null', 'None', '0', '0.0')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.rating')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.rating')) AS DECIMAL(10,2)) * 100
                                ELSE NULL
                            END AS gamelist_rating
                        FROM roms r
                    ) AS r;
                """)
        )


def downgrade():
    connection = op.get_bind()
    if is_postgresql(connection):
        connection.execute(
            sa.text("""
                CREATE OR REPLACE VIEW roms_metadata AS
                SELECT
                    r.id AS rom_id,
                    NOW() AS created_at,
                    NOW() AS updated_at,
                    COALESCE(
                        NULLIF(r.manual_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.igdb_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.moby_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.ss_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.launchbox_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.ra_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.flashpoint_metadata -> 'genres', '[]'::jsonb),
                        NULLIF(r.gamelist_metadata -> 'genres', '[]'::jsonb),
                        '[]'::jsonb
                    ) AS genres,

                    COALESCE(
                        NULLIF(r.manual_metadata -> 'franchises', '[]'::jsonb),
                        NULLIF(r.igdb_metadata -> 'franchises', '[]'::jsonb),
                        NULLIF(r.ss_metadata -> 'franchises', '[]'::jsonb),
                        NULLIF(r.flashpoint_metadata -> 'franchises', '[]'::jsonb),
                        NULLIF(r.gamelist_metadata -> 'franchises', '[]'::jsonb),
                        '[]'::jsonb
                    ) AS franchises,

                    COALESCE(
                        (r.igdb_metadata -> 'collections'),
                        '[]'::jsonb
                    ) AS collections,

                    COALESCE(
                        NULLIF(r.manual_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.igdb_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.ss_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.ra_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.launchbox_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.flashpoint_metadata -> 'companies', '[]'::jsonb),
                        NULLIF(r.gamelist_metadata -> 'companies', '[]'::jsonb),
                        '[]'::jsonb
                    ) AS companies,

                    COALESCE(
                        NULLIF(r.manual_metadata -> 'game_modes', '[]'::jsonb),
                        NULLIF(r.igdb_metadata -> 'game_modes', '[]'::jsonb),
                        NULLIF(r.ss_metadata -> 'game_modes', '[]'::jsonb),
                        NULLIF(r.flashpoint_metadata -> 'game_modes', '[]'::jsonb),
                        '[]'::jsonb
                    ) AS game_modes,

                    COALESCE(
                        (r.manual_metadata -> 'age_ratings'),
                        CASE
                            WHEN r.igdb_metadata IS NOT NULL
                                AND r.igdb_metadata ? 'age_ratings'
                                AND jsonb_array_length(r.igdb_metadata -> 'age_ratings') > 0
                            THEN
                                jsonb_path_query_array(r.igdb_metadata, '$.age_ratings[*].rating')
                            ELSE
                                NULL
                        END,
                        CASE
                            WHEN r.ss_metadata IS NOT NULL
                                AND r.ss_metadata ? 'age_ratings'
                                AND jsonb_array_length(r.ss_metadata -> 'age_ratings') > 0
                            THEN
                                jsonb_path_query_array(r.ss_metadata, '$.age_ratings[*].rating')
                            ELSE
                                NULL
                        END,
                        CASE
                            WHEN r.launchbox_metadata IS NOT NULL
                                AND r.launchbox_metadata ? 'esrb'
                                AND r.launchbox_metadata ->> 'esrb' IS NOT NULL
                                AND r.launchbox_metadata ->> 'esrb' != ''
                            THEN
                                jsonb_build_array(r.launchbox_metadata ->> 'esrb')
                            ELSE
                                NULL
                        END,
                        '[]'::jsonb
                    ) AS age_ratings,

                    CASE
                        WHEN r.manual_metadata IS NOT NULL AND r.manual_metadata ? 'first_release_date' AND
                            r.manual_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.manual_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.manual_metadata ->> 'first_release_date')::bigint

                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'first_release_date' AND
                            r.igdb_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.igdb_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.igdb_metadata ->> 'first_release_date')::bigint * 1000

                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'first_release_date' AND
                            r.ss_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.ss_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.ss_metadata ->> 'first_release_date')::bigint * 1000

                        WHEN r.launchbox_metadata IS NOT NULL AND r.launchbox_metadata ? 'release_date' AND
                            r.launchbox_metadata ->> 'release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.launchbox_metadata ->> 'release_date' ~ '^[0-9]+$'
                        THEN (r.launchbox_metadata ->> 'release_date')::bigint

                        WHEN r.flashpoint_metadata IS NOT NULL AND r.flashpoint_metadata ? 'release_date' AND
                            r.flashpoint_metadata ->> 'release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.flashpoint_metadata ->> 'release_date' ~ '^[0-9]+$'
                        THEN (r.flashpoint_metadata ->> 'release_date')::bigint

                        WHEN r.gamelist_metadata IS NOT NULL AND r.gamelist_metadata ? 'releasedate' AND
                            r.gamelist_metadata ->> 'releasedate' NOT IN ('null', 'None', '0', '0.0') AND
                            r.gamelist_metadata ->> 'releasedate' ~ '^[0-9]+$'
                        THEN (r.gamelist_metadata ->> 'releasedate')::bigint

                        ELSE NULL
                    END AS first_release_date,

                    COALESCE(
                        NULLIF(r.manual_metadata ->> 'player_count', ''),
                        NULLIF(r.igdb_metadata ->> 'player_count', ''),
                        NULLIF(r.ss_metadata ->> 'player_count', ''),
                        NULLIF(r.launchbox_metadata ->> 'max_players', ''),
                        '1'
                    ) AS player_count,

                    COALESCE(
                        NULLIF((
                            SELECT GREATEST(
                                COALESCE(igdb_rating, 0),
                                COALESCE(ss_rating, 0),
                                COALESCE(launchbox_rating, 0),
                                COALESCE(gamelist_rating, 0)
                            )
                        ), 0),
                        NULL
                    ) AS average_rating
                FROM (
                    SELECT
                        r.*,
                        CASE
                            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'total_rating' AND
                                r.igdb_metadata ->> 'total_rating' NOT IN ('null', 'None', '0', '0.0') AND
                                r.igdb_metadata ->> 'total_rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.igdb_metadata ->> 'total_rating')::float
                            ELSE NULL
                        END AS igdb_rating,
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
                        END AS launchbox_rating,
                        CASE
                            WHEN r.gamelist_metadata IS NOT NULL AND r.gamelist_metadata ? 'rating' AND
                                r.gamelist_metadata ->> 'rating' NOT IN ('null', 'None', '0', '0.0') AND
                                r.gamelist_metadata ->> 'rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.gamelist_metadata ->> 'rating')::float * 100
                            ELSE NULL
                        END AS gamelist_rating
                    FROM roms r
                ) AS r;
                """)
        )
    else:
        connection.execute(
            sa.text("""
                CREATE OR REPLACE VIEW roms_metadata AS
                    SELECT
                        r.id as rom_id,
                        NOW() AS created_at,
                        NOW() AS updated_at,
                        COALESCE(
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.moby_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.moby_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.launchbox_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.launchbox_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ra_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.ra_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.genres') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.gamelist_metadata, '$.genres')) > 0 THEN JSON_EXTRACT(r.gamelist_metadata, '$.genres') ELSE NULL END,
                            JSON_ARRAY()
                        ) AS genres,

                        COALESCE(
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.franchises') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.franchises') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.franchises') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.franchises') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.gamelist_metadata, '$.franchises')) > 0 THEN JSON_EXTRACT(r.gamelist_metadata, '$.franchises') ELSE NULL END,
                            JSON_ARRAY()
                        ) AS franchises,

                        COALESCE(
                            JSON_EXTRACT(r.igdb_metadata, '$.collections'),
                            JSON_ARRAY()
                        ) AS collections,

                        COALESCE(
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ra_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.ra_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.launchbox_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.launchbox_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.companies') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.gamelist_metadata, '$.companies')) > 0 THEN JSON_EXTRACT(r.gamelist_metadata, '$.companies') ELSE NULL END,
                            JSON_ARRAY()
                        ) AS companies,

                        COALESCE(
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.manual_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.manual_metadata, '$.game_modes') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.igdb_metadata, '$.game_modes') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.ss_metadata, '$.game_modes') ELSE NULL END,
                            CASE WHEN JSON_LENGTH(JSON_EXTRACT(r.flashpoint_metadata, '$.game_modes')) > 0 THEN JSON_EXTRACT(r.flashpoint_metadata, '$.game_modes') ELSE NULL END,
                            JSON_ARRAY()
                        ) AS game_modes,

                        COALESCE(
                            JSON_EXTRACT(r.manual_metadata, '$.age_ratings'),
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.age_ratings')
                                    AND JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings')) > 0
                                THEN
                                     IF(
                                        JSON_TYPE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                                        JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating'),
                                        JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')))
                                    )
                                ELSE
                                    NULL
                            END,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.age_ratings')
                                    AND JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.age_ratings')) > 0
                                THEN
                                     IF(
                                        JSON_TYPE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                                        JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating'),
                                        JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')))
                                    )
                                ELSE
                                    NULL
                            END,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.esrb')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.esrb')) IS NOT NULL
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.esrb')) != ''
                                THEN JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.esrb')))
                                ELSE NULL
                            END,
                            JSON_ARRAY()
                        ) AS age_ratings,

                        CASE
                            WHEN JSON_CONTAINS_PATH(r.manual_metadata, 'one', '$.first_release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) AS UNSIGNED)

                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.first_release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) AS UNSIGNED) * 1000

                            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.first_release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) AS UNSIGNED) * 1000

                            WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.release_date')) AS UNSIGNED)

                            WHEN JSON_CONTAINS_PATH(r.flashpoint_metadata, 'one', '$.release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.release_date')) AS UNSIGNED)

                            WHEN JSON_CONTAINS_PATH(r.gamelist_metadata, 'one', '$.releasedate')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.releasedate')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.releasedate')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.releasedate')) AS UNSIGNED)

                            ELSE NULL
                        END AS first_release_date,

                        COALESCE(
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.player_count')), ''),
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.player_count')), ''),
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.player_count')), ''),
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.max_players')), ''),
                            '1'
                        ) AS player_count,

                        COALESCE(
                            NULLIF(GREATEST(
                                COALESCE(igdb_rating, 0),
                                COALESCE(ss_rating, 0),
                                COALESCE(launchbox_rating, 0),
                                COALESCE(gamelist_rating, 0)
                            ), 0),
                            NULL
                        ) AS average_rating
                    FROM (
                        SELECT
                            r.*,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.total_rating')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.total_rating')) NOT IN ('null', 'None', '0', '0.0')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.total_rating')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.total_rating')) AS DECIMAL(10,2))
                                ELSE NULL
                            END AS igdb_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.ss_score')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.ss_score')) NOT IN ('null', 'None', '0', '0.0')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.ss_score')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.ss_score')) AS DECIMAL(10,2)) * 10
                                ELSE NULL
                            END AS ss_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.community_rating')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.community_rating')) NOT IN ('null', 'None', '0', '0.0')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.community_rating')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.community_rating')) AS DECIMAL(10,2)) * 20
                                ELSE NULL
                            END AS launchbox_rating,
                            CASE
                                WHEN JSON_CONTAINS_PATH(r.gamelist_metadata, 'one', '$.rating')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.rating')) NOT IN ('null', 'None', '0', '0.0')
                                    AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.rating')) REGEXP '^[0-9]+(\\.[0-9]+)?$'
                                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.rating')) AS DECIMAL(10,2)) * 100
                                ELSE NULL
                            END AS gamelist_rating
                        FROM roms r
                    ) AS r;
                """)
        )
