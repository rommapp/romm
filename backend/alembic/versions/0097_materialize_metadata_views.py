"""Materialize roms_metadata and virtual_collections into real tables

Both were SQL views that re-derived their contents from the raw provider
metadata JSON on every query, making galleries, search and the collections
index take seconds to minutes on large libraries (issue #3768). Replace them
with real tables, populated once here and maintained at scan/edit/delete time
by handler.database.materialized_metadata.

Revision ID: 0097_materialize_metadata_views
Revises: 0096_fix_virtual_collections
Create Date: 2026-07-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

from handler.database.materialized_metadata import (
    refresh_roms_metadata,
    refresh_virtual_collections,
)
from utils.database import CustomJSON, is_postgresql

# revision identifiers, used by Alembic.
revision = "0097_materialize_metadata_views"
down_revision = "0096_fix_virtual_collections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    # Drop the dependent view first, then the base view.
    op.execute("DROP VIEW IF EXISTS virtual_collections")
    op.execute("DROP VIEW IF EXISTS roms_metadata")

    op.create_table(
        "roms_metadata",
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("genres", CustomJSON(), nullable=True),
        sa.Column("franchises", CustomJSON(), nullable=True),
        sa.Column("collections", CustomJSON(), nullable=True),
        sa.Column("companies", CustomJSON(), nullable=True),
        sa.Column("game_modes", CustomJSON(), nullable=True),
        sa.Column("age_ratings", CustomJSON(), nullable=True),
        sa.Column("player_count", sa.String(length=100), nullable=True),
        sa.Column("first_release_date", sa.BigInteger(), nullable=True),
        sa.Column("average_rating", sa.Float(), nullable=True),
        sa.Column("platform_id", sa.Integer(), nullable=True),
        sa.Column("regions", CustomJSON(), nullable=True),
        sa.Column("languages", CustomJSON(), nullable=True),
        sa.Column("tags", CustomJSON(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rom_id"),
    )
    op.create_index("idx_roms_metadata_platform_id", "roms_metadata", ["platform_id"])
    op.create_index(
        "idx_roms_metadata_first_release_date", "roms_metadata", ["first_release_date"]
    )
    op.create_index(
        "idx_roms_metadata_average_rating", "roms_metadata", ["average_rating"]
    )

    op.create_table(
        "virtual_collections",
        sa.Column("name", sa.String(length=400), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("path_covers_s", CustomJSON(), nullable=True),
        sa.Column("path_covers_l", CustomJSON(), nullable=True),
        sa.Column("rom_ids", CustomJSON(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("name", "type"),
    )
    op.create_index("idx_virtual_collections_type", "virtual_collections", ["type"])

    # Populate from the raw metadata (roms_metadata first; virtual_collections
    # reads from it).
    session = Session(bind=connection)
    refresh_roms_metadata(session)
    refresh_virtual_collections(session)


def downgrade() -> None:
    connection = op.get_bind()

    # DROP TABLE removes the tables' indexes and foreign keys with them.
    op.execute("DROP TABLE IF EXISTS virtual_collections")
    op.execute("DROP TABLE IF EXISTS roms_metadata")

    _recreate_roms_metadata_view(connection)
    _recreate_virtual_collections_view(connection)


def _recreate_roms_metadata_view(connection) -> None:
    """Recreate the roms_metadata view as defined at revision 0096 (from 0074)."""
    if is_postgresql(connection):
        connection.execute(sa.text("""
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
                    COALESCE((r.igdb_metadata -> 'collections'), '[]'::jsonb) AS collections,
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
                        CASE WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'age_ratings'
                            AND jsonb_array_length(r.igdb_metadata -> 'age_ratings') > 0
                            THEN jsonb_path_query_array(r.igdb_metadata, '$.age_ratings[*].rating') ELSE NULL END,
                        CASE WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'age_ratings'
                            AND jsonb_array_length(r.ss_metadata -> 'age_ratings') > 0
                            THEN jsonb_path_query_array(r.ss_metadata, '$.age_ratings[*].rating') ELSE NULL END,
                        CASE WHEN r.launchbox_metadata IS NOT NULL AND r.launchbox_metadata ? 'esrb'
                            AND r.launchbox_metadata ->> 'esrb' IS NOT NULL AND r.launchbox_metadata ->> 'esrb' != ''
                            THEN jsonb_build_array(r.launchbox_metadata ->> 'esrb') ELSE NULL END,
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
                        WHEN r.ra_metadata IS NOT NULL AND r.ra_metadata ? 'first_release_date' AND
                            r.ra_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.ra_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.ra_metadata ->> 'first_release_date')::bigint * 1000
                        WHEN r.launchbox_metadata IS NOT NULL AND r.launchbox_metadata ? 'first_release_date' AND
                            r.launchbox_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.launchbox_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.launchbox_metadata ->> 'first_release_date')::bigint * 1000
                        WHEN r.flashpoint_metadata IS NOT NULL AND r.flashpoint_metadata ? 'first_release_date' AND
                            r.flashpoint_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0') AND
                            r.flashpoint_metadata ->> 'first_release_date' ~ '^[0-9]+$'
                        THEN (r.flashpoint_metadata ->> 'first_release_date')::bigint * 1000
                        WHEN r.gamelist_metadata IS NOT NULL AND r.gamelist_metadata ? 'first_release_date'
                            AND r.gamelist_metadata ->> 'first_release_date' NOT IN ('null', 'None', '0', '0.0')
                            AND r.gamelist_metadata ->> 'first_release_date' ~ '^[0-9]{8}T[0-9]{6}$'
                        THEN (extract(epoch FROM to_timestamp(r.gamelist_metadata ->> 'first_release_date', 'YYYYMMDD"T"HH24MISS')) * 1000)::bigint
                        ELSE NULL
                    END AS first_release_date,
                    CASE
                        WHEN (igdb_rating IS NOT NULL OR moby_rating IS NOT NULL OR ss_rating IS NOT NULL OR launchbox_rating IS NOT NULL OR gamelist_rating IS NOT NULL) THEN
                            (COALESCE(igdb_rating, 0) + COALESCE(moby_rating, 0) + COALESCE(ss_rating, 0) + COALESCE(launchbox_rating, 0) + COALESCE(gamelist_rating, 0)) /
                            (CASE WHEN igdb_rating IS NOT NULL THEN 1 ELSE 0 END +
                            CASE WHEN moby_rating IS NOT NULL THEN 1 ELSE 0 END +
                            CASE WHEN ss_rating IS NOT NULL THEN 1 ELSE 0 END +
                            CASE WHEN launchbox_rating IS NOT NULL THEN 1 ELSE 0 END +
                            CASE WHEN gamelist_rating IS NOT NULL THEN 1 ELSE 0 END)
                        ELSE NULL
                    END AS average_rating,
                    COALESCE(
                        NULLIF(r.manual_metadata ->> 'player_count', '1'),
                        NULLIF(r.ss_metadata ->> 'player_count', '1'),
                        NULLIF(r.igdb_metadata ->> 'player_count', '1'),
                        NULLIF(r.gamelist_metadata ->> 'player_count', '1'),
                        '1'
                    ) AS player_count
                FROM (
                    SELECT r.id, r.manual_metadata, r.igdb_metadata, r.moby_metadata, r.ss_metadata,
                        r.ra_metadata, r.launchbox_metadata, r.flashpoint_metadata, r.gamelist_metadata,
                        CASE WHEN r.igdb_metadata IS NOT NULL AND r.igdb_metadata ? 'total_rating' AND
                            r.igdb_metadata ->> 'total_rating' NOT IN ('null', 'None', '0', '0.0') AND
                            r.igdb_metadata ->> 'total_rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.igdb_metadata ->> 'total_rating')::float ELSE NULL END AS igdb_rating,
                        CASE WHEN r.moby_metadata IS NOT NULL AND r.moby_metadata ? 'moby_score' AND
                            r.moby_metadata ->> 'moby_score' NOT IN ('null', 'None', '0', '0.0') AND
                            r.moby_metadata ->> 'moby_score' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.moby_metadata ->> 'moby_score')::float * 10 ELSE NULL END AS moby_rating,
                        CASE WHEN r.ss_metadata IS NOT NULL AND r.ss_metadata ? 'ss_score' AND
                            r.ss_metadata ->> 'ss_score' NOT IN ('null', 'None', '0', '0.0') AND
                            r.ss_metadata ->> 'ss_score' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.ss_metadata ->> 'ss_score')::float * 10 ELSE NULL END AS ss_rating,
                        CASE WHEN r.launchbox_metadata IS NOT NULL AND r.launchbox_metadata ? 'community_rating' AND
                            r.launchbox_metadata ->> 'community_rating' NOT IN ('null', 'None', '0', '0.0') AND
                            r.launchbox_metadata ->> 'community_rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.launchbox_metadata ->> 'community_rating')::float * 20 ELSE NULL END AS launchbox_rating,
                        CASE WHEN r.gamelist_metadata IS NOT NULL AND r.gamelist_metadata ? 'rating' AND
                            r.gamelist_metadata ->> 'rating' NOT IN ('null', 'None', '0', '0.0') AND
                            r.gamelist_metadata ->> 'rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                            THEN (r.gamelist_metadata ->> 'rating')::float * 100 ELSE NULL END AS gamelist_rating
                    FROM roms r
                ) AS r;
            """))
    else:
        connection.execute(sa.text("""
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
                        COALESCE(JSON_EXTRACT(r.igdb_metadata, '$.collections'), JSON_ARRAY()) AS collections,
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
                            CASE WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.age_ratings')
                                AND JSON_LENGTH(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings')) > 0
                                THEN IF(JSON_TYPE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                                    JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating'),
                                    JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')))) ELSE NULL END,
                            CASE WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.age_ratings')
                                AND JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.age_ratings')) > 0
                                THEN IF(JSON_TYPE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                                    JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating'),
                                    JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')))) ELSE NULL END,
                            CASE WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.esrb')
                                AND JSON_EXTRACT(r.launchbox_metadata, '$.esrb') IS NOT NULL
                                AND JSON_EXTRACT(r.launchbox_metadata, '$.esrb') != ''
                                THEN JSON_ARRAY(JSON_EXTRACT(r.launchbox_metadata, '$.esrb')) ELSE NULL END,
                            JSON_ARRAY()
                        ) AS age_ratings,
                        CASE
                            WHEN JSON_CONTAINS_PATH(r.manual_metadata, 'one', '$.first_release_date') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_EXTRACT(r.manual_metadata, '$.first_release_date') AS SIGNED)
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
                            WHEN JSON_CONTAINS_PATH(r.flashpoint_metadata, 'one', '$.first_release_date') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
                            THEN CAST(JSON_EXTRACT(r.flashpoint_metadata, '$.first_release_date') AS SIGNED) * 1000
                            WHEN JSON_CONTAINS_PATH(r.gamelist_metadata, 'one', '$.first_release_date')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0')
                                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.first_release_date')) REGEXP '^[0-9]{8}T[0-9]{6}$'
                            THEN UNIX_TIMESTAMP(STR_TO_DATE(JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.first_release_date')), '%Y%m%dT%H%i%S')) * 1000
                            ELSE NULL
                        END AS first_release_date,
                        CASE
                            WHEN (igdb_rating IS NOT NULL OR moby_rating IS NOT NULL OR ss_rating IS NOT NULL OR launchbox_rating IS NOT NULL OR gamelist_rating IS NOT NULL) THEN
                                (COALESCE(igdb_rating, 0) + COALESCE(moby_rating, 0) + COALESCE(ss_rating, 0) + COALESCE(launchbox_rating, 0) + COALESCE(gamelist_rating, 0)) /
                                (CASE WHEN igdb_rating IS NOT NULL THEN 1 ELSE 0 END +
                                CASE WHEN moby_rating IS NOT NULL THEN 1 ELSE 0 END +
                                CASE WHEN ss_rating IS NOT NULL THEN 1 ELSE 0 END +
                                CASE WHEN launchbox_rating IS NOT NULL THEN 1 ELSE 0 END +
                                CASE WHEN gamelist_rating IS NOT NULL THEN 1 ELSE 0 END)
                            ELSE NULL
                        END AS average_rating,
                        COALESCE(
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.player_count')), '1'),
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.player_count')), '1'),
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.player_count')), '1'),
                            NULLIF(JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.player_count')), '1'),
                            '1'
                        ) AS player_count
                    FROM (
                        SELECT id, manual_metadata, igdb_metadata, moby_metadata, ss_metadata, ra_metadata,
                            launchbox_metadata, flashpoint_metadata, gamelist_metadata,
                            CASE WHEN JSON_CONTAINS_PATH(igdb_metadata, 'one', '$.total_rating') AND
                                JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(igdb_metadata, '$.total_rating') AS DECIMAL(10,2)) ELSE NULL END AS igdb_rating,
                            CASE WHEN JSON_CONTAINS_PATH(moby_metadata, 'one', '$.moby_score') AND
                                JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(moby_metadata, '$.moby_score') AS DECIMAL(10,2)) * 10 ELSE NULL END AS moby_rating,
                            CASE WHEN JSON_CONTAINS_PATH(ss_metadata, 'one', '$.ss_score') AND
                                JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(ss_metadata, '$.ss_score') AS DECIMAL(10,2)) * 10 ELSE NULL END AS ss_rating,
                            CASE WHEN JSON_CONTAINS_PATH(launchbox_metadata, 'one', '$.community_rating') AND
                                JSON_UNQUOTE(JSON_EXTRACT(launchbox_metadata, '$.community_rating')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(launchbox_metadata, '$.community_rating')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(launchbox_metadata, '$.community_rating') AS DECIMAL(10,2)) * 20 ELSE NULL END AS launchbox_rating,
                            CASE WHEN JSON_CONTAINS_PATH(gamelist_metadata, 'one', '$.rating') AND
                                JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.rating')) NOT IN ('null', 'None', '0', '0.0') AND
                                JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.rating')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                                THEN CAST(JSON_EXTRACT(gamelist_metadata, '$.rating') AS DECIMAL(10,2)) * 100 ELSE NULL END AS gamelist_rating
                        FROM roms
                    ) AS r;
            """))


def _recreate_virtual_collections_view(connection) -> None:
    """Recreate the virtual_collections view as defined at revision 0096."""
    if is_postgresql(connection):
        connection.execute(sa.text("""
                CREATE OR REPLACE VIEW virtual_collections AS
                WITH base AS (
                    SELECT r.id as rom_id, r.path_cover_s, r.path_cover_l,
                        rm.genres, rm.franchises, rm.collections, rm.game_modes, rm.companies
                    FROM roms r JOIN roms_metadata rm ON rm.rom_id = r.id
                ),
                genres_collection AS (SELECT rom_id, path_cover_s, path_cover_l, jsonb_array_elements_text(genres) as collection_name, 'genre' as collection_type FROM base),
                franchises_collection AS (SELECT rom_id, path_cover_s, path_cover_l, jsonb_array_elements_text(franchises) as collection_name, 'franchise' as collection_type FROM base),
                collection_collection AS (SELECT rom_id, path_cover_s, path_cover_l, jsonb_array_elements_text(collections) as collection_name, 'collection' as collection_type FROM base),
                modes_collection AS (SELECT rom_id, path_cover_s, path_cover_l, jsonb_array_elements_text(game_modes) as collection_name, 'mode' as collection_type FROM base),
                companies_collection AS (SELECT rom_id, path_cover_s, path_cover_l, jsonb_array_elements_text(companies) as collection_name, 'company' as collection_type FROM base)
                SELECT collection_name as name, collection_type as type,
                    'Autogenerated ' || collection_type || ' collection' AS description,
                    NOW() AS created_at, NOW() AS updated_at,
                    jsonb_agg(rom_id) as rom_ids, jsonb_agg(path_cover_s) as path_covers_s, jsonb_agg(path_cover_l) as path_covers_l
                FROM (
                    SELECT * FROM genres_collection UNION ALL SELECT * FROM franchises_collection
                    UNION ALL SELECT * FROM collection_collection UNION ALL SELECT * FROM modes_collection
                    UNION ALL SELECT * FROM companies_collection
                ) combined
                GROUP BY collection_type, collection_name
                HAVING COUNT(DISTINCT rom_id) > 2
                ORDER BY collection_type, collection_name;
            """))
    else:
        connection.execute(sa.text("""
                CREATE OR REPLACE VIEW virtual_collections AS
                WITH base AS (
                    SELECT r.id as rom_id, r.path_cover_s, r.path_cover_l,
                        rm.genres, rm.franchises, rm.collections, rm.game_modes, rm.companies
                    FROM roms r JOIN roms_metadata rm ON rm.rom_id = r.id
                ),
                genres AS (SELECT base.rom_id, base.path_cover_s, base.path_cover_l, CONCAT(j.genre) COLLATE utf8mb4_general_ci as collection_name, 'genre' COLLATE utf8mb4_general_ci as collection_type FROM base CROSS JOIN JSON_TABLE(base.genres, '$[*]' COLUMNS (genre VARCHAR(255) PATH '$')) j),
                franchises AS (SELECT base.rom_id, base.path_cover_s, base.path_cover_l, CONCAT(j.franchise) COLLATE utf8mb4_general_ci as collection_name, 'franchise' COLLATE utf8mb4_general_ci as collection_type FROM base CROSS JOIN JSON_TABLE(base.franchises, '$[*]' COLUMNS (franchise VARCHAR(255) PATH '$')) j),
                collections AS (SELECT base.rom_id, base.path_cover_s, base.path_cover_l, CONCAT(j.collection) COLLATE utf8mb4_general_ci as collection_name, 'collection' COLLATE utf8mb4_general_ci as collection_type FROM base CROSS JOIN JSON_TABLE(base.collections, '$[*]' COLUMNS (collection VARCHAR(255) PATH '$')) j),
                modes AS (SELECT base.rom_id, base.path_cover_s, base.path_cover_l, CONCAT(j.mode) COLLATE utf8mb4_general_ci as collection_name, 'mode' COLLATE utf8mb4_general_ci as collection_type FROM base CROSS JOIN JSON_TABLE(base.game_modes, '$[*]' COLUMNS (mode VARCHAR(255) PATH '$')) j),
                companies AS (SELECT base.rom_id, base.path_cover_s, base.path_cover_l, CONCAT(j.company) COLLATE utf8mb4_general_ci as collection_name, 'company' COLLATE utf8mb4_general_ci as collection_type FROM base CROSS JOIN JSON_TABLE(base.companies, '$[*]' COLUMNS (company VARCHAR(255) PATH '$')) j)
                SELECT collection_name as name, collection_type as type,
                    CONCAT('Autogenerated ', collection_name, ' collection') COLLATE utf8mb4_general_ci AS description,
                    NOW() AS created_at, NOW() AS updated_at,
                    JSON_ARRAYAGG(rom_id) as rom_ids, JSON_ARRAYAGG(path_cover_s) as path_covers_s, JSON_ARRAYAGG(path_cover_l) as path_covers_l
                FROM (
                    SELECT * FROM genres UNION ALL SELECT * FROM franchises UNION ALL SELECT * FROM collections
                    UNION ALL SELECT * FROM modes UNION ALL SELECT * FROM companies
                ) combined
                GROUP BY collection_type, collection_name
                HAVING COUNT(DISTINCT rom_id) > 2
                ORDER BY collection_type, collection_name;
            """))
