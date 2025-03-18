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
                    r.id as rom_id,
                    -- Genres
                    COALESCE(
                        (r.igdb_metadata -> 'genres'),
                        (r.moby_metadata -> 'genres'),
                        (r.ss_metadata -> 'genres'),
                        '[]'::jsonb
                    ) AS genres,

                    -- Franchises
                    CASE 
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'franchises' THEN r.igdb_metadata -> 'franchises'
                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'franchises' THEN r.ss_metadata -> 'franchises'
                        ELSE '[]'::jsonb
                    END AS franchises,

                    -- Collections
                    CASE 
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'collections' THEN r.igdb_metadata -> 'collections'
                        ELSE '[]'::jsonb
                    END AS collections,

                    -- Companies
                    CASE 
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'companies' THEN r.igdb_metadata -> 'companies'
                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'companies' THEN r.ss_metadata -> 'companies'
                        ELSE '[]'::jsonb
                    END AS companies,

                    -- Game Modes
                    CASE 
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'game_modes' THEN r.igdb_metadata -> 'game_modes'
                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'game_modes' THEN r.ss_metadata -> 'game_modes'
                        ELSE '[]'::jsonb
                    END AS game_modes,

                    -- Age Ratings
                    (
                        SELECT jsonb_agg(rating -> 'rating')
                        FROM jsonb_array_elements(
                            CASE WHEN r.igdb_metadata ? 'age_ratings' 
                                THEN r.igdb_metadata -> 'age_ratings' 
                                ELSE '[]'::jsonb 
                            END
                        ) AS rating
                    ) AS age_ratings,

                    -- YouTube Video ID
                    CASE 
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'youtube_video_id' 
                        THEN r.igdb_metadata ->> 'youtube_video_id'
                        ELSE ''
                    END AS youtube_video_id,

                    -- Alternative Names
                    COALESCE(
                        (r.igdb_metadata -> 'alternative_names'),
                        (r.moby_metadata -> 'alternate_titles'),
                        (r.ss_metadata -> 'alternative_names'),
                        '[]'::jsonb
                    ) AS alternative_names,

                    -- First Release Date
                    CASE 
                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'first_release_date' 
                        THEN (r.igdb_metadata ->> 'first_release_date')::bigint * 1000
                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'first_release_date' 
                        THEN (r.ss_metadata ->> 'first_release_date')::bigint * 1000
                        ELSE NULL
                    END AS first_release_date,

                    -- Average Rating
                    CASE 
                        WHEN (
                            (r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'total_rating') OR
                            (r.moby_metadata IS NOT NULL AND r.moby_metadata ? 'moby_score') OR
                            (r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'ss_score')
                        ) THEN (
                            SELECT 
                                CASE 
                                    WHEN COUNT(r) > 0 THEN SUM(r) / COUNT(r)
                                    ELSE NULL
                                END
                            FROM (
                                SELECT 
                                    CASE 
                                        WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'total_rating' 
                                        THEN (r.igdb_metadata ->> 'total_rating')::float
                                        ELSE NULL
                                    END AS r
                                UNION ALL
                                SELECT 
                                    CASE 
                                        WHEN r.moby_metadata IS NOT NULL AND r.moby_metadata ? 'moby_score' 
                                        THEN (r.moby_metadata ->> 'moby_score')::float * 10
                                        ELSE NULL
                                    END
                                UNION ALL
                                SELECT 
                                    CASE 
                                        WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'ss_score' 
                                        THEN (r.ss_metadata ->> 'ss_score')::float
                                        ELSE NULL
                                    END
                            ) AS ratings
                            WHERE r IS NOT NULL AND r != 0
                        )
                        ELSE NULL
                    END AS average_rating
                FROM roms r;
                """
            )
        )
    else:
        connection.execute(
            sa.text(
                """CREATE OR REPLACE VIEW roms_metadata AS
                    SELECT 
                        r.id as rom_id,
                        -- Genres
                        COALESCE(
                            CASE WHEN r.igdb_metadata IS NOT NULL THEN r.igdb_metadata->'genres' END,
                            CASE WHEN r.moby_metadata IS NOT NULL THEN r.moby_metadata->'genres' END,
                            CASE WHEN r.ss_metadata IS NOT NULL THEN r.ss_metadata->'genres' END,
                            '[]'
                        ) AS genres,

                        -- Franchises
                        CASE 
                            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'franchises' THEN r.igdb_metadata->'franchises'
                            WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'franchises' THEN r.ss_metadata->'franchises'
                            ELSE '[]'
                        END AS franchises,

                        -- Collections
                        CASE 
                            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'collections' THEN r.igdb_metadata->'collections'
                            ELSE '[]'
                        END AS collections,

                        -- Companies
                        CASE 
                            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'companies' THEN r.igdb_metadata->'companies'
                            WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'companies' THEN r.ss_metadata->'companies'
                            ELSE '[]'
                        END AS companies,

                        -- Game Modes
                        CASE 
                            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'game_modes' THEN r.igdb_metadata->'game_modes'
                            WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'game_modes' THEN r.ss_metadata->'game_modes'
                            ELSE '[]'
                        END AS game_modes,

                        -- Age Ratings (PostgreSQL syntax)
                        CASE 
                            WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'age_ratings' THEN 
                                (SELECT jsonb_agg(rating->'rating')
                                FROM jsonb_array_elements(r.igdb_metadata->'age_ratings') AS rating)
                            ELSE '[]'
                        END AS age_ratings,

                        -- YouTube Video ID
                        CASE 
                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.youtube_video_id') 
                            THEN JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.youtube_video_id'))
                            ELSE ''
                        END AS youtube_video_id,

                        -- Alternative Names
                        COALESCE(
                            JSON_EXTRACT(r.igdb_metadata, '$.alternative_names'),
                            JSON_EXTRACT(r.moby_metadata, '$.alternate_titles'),
                            JSON_EXTRACT(r.ss_metadata, '$.alternative_names'),
                            JSON_ARRAY()
                        ) AS alternative_names,

                        -- First Release Date
                        CASE 
                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.first_release_date') 
                            THEN CAST(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date') AS SIGNED) * 1000
                            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.first_release_date') 
                            THEN CAST(JSON_EXTRACT(r.ss_metadata, '$.first_release_date') AS SIGNED) * 1000
                            ELSE NULL
                        END AS first_release_date,

                        -- Average Rating
                        (
                            WITH ratings AS (
                                SELECT r FROM (
                                    SELECT 
                                        CASE 
                                            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.total_rating') 
                                            THEN CAST(JSON_EXTRACT(r.igdb_metadata, '$.total_rating') AS DECIMAL(10,2))
                                            ELSE NULL
                                        END AS r
                                    UNION ALL
                                    SELECT 
                                        CASE 
                                            WHEN JSON_CONTAINS_PATH(r.moby_metadata, 'one', '$.moby_score') 
                                            THEN CAST(JSON_EXTRACT(r.moby_metadata, '$.moby_score') AS DECIMAL(10,2)) * 10
                                            ELSE NULL
                                        END
                                    UNION ALL
                                    SELECT 
                                        CASE 
                                            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.ss_score') 
                                            THEN CAST(JSON_EXTRACT(r.ss_metadata, '$.ss_score') AS DECIMAL(10,2))
                                            ELSE NULL
                                        END
                                ) AS rating_values
                                WHERE r IS NOT NULL AND r != 0
                            )
                            SELECT 
                                CASE 
                                    WHEN COUNT(*) > 0 FROM ratings THEN AVG(r) FROM ratings
                                    ELSE NULL
                                END
                        ) AS average_rating
                    FROM roms r;
                """
            )
        )


def downgrade():
    op.execute("DROP VIEW IF EXISTS roms_metadata")
