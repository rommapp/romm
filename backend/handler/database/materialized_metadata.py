"""Materialized `roms_metadata` and `virtual_collections` maintenance.

Both used to be SQL views that re-derived their contents from the raw provider
metadata JSON on every query, which made galleries, search and the collections
index take seconds to minutes on large libraries (issue #3768). They are now
real tables, built once by migration ``0097`` and kept in sync here:

- ``refresh_roms_metadata`` recomputes one rom's (or every rom's) facet row
  using the exact derivation the old view used. It is cheap per rom and runs
  synchronously on the rom write paths.
- ``refresh_virtual_collections`` rebuilds the whole aggregation table. It is a
  full-library pass, so it is driven from a debounced background job rather than
  inline on every edit.

This module is the single source of truth for the derivation SQL: both the
migration and the runtime write paths import from here. A future change to the
derivation rules ships a new migration that calls ``refresh_roms_metadata`` /
``refresh_virtual_collections`` to rebuild.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session

from utils.database import is_postgresql

# Rom columns whose contents feed the virtual_collections aggregation
# (its genres/franchises/collections/game_modes/companies all derive from these
# metadata blobs). A rom update only needs to trigger a rebuild when it touches
# one of these; cover/path-only updates during a scan do not.
VIRTUAL_COLLECTION_SOURCE_COLUMNS = frozenset(
    {
        "manual_metadata",
        "igdb_metadata",
        "moby_metadata",
        "ss_metadata",
        "ra_metadata",
        "launchbox_metadata",
        "flashpoint_metadata",
        "gamelist_metadata",
    }
)

# Columns recomputed on every refresh. Excludes ``rom_id`` (the conflict key)
# and ``created_at`` (preserved across updates).
_ROMS_METADATA_UPSERT_COLUMNS = (
    "genres",
    "franchises",
    "collections",
    "companies",
    "game_modes",
    "age_ratings",
    "first_release_date",
    "average_rating",
    "player_count",
    "platform_id",
    "regions",
    "languages",
    "tags",
    "updated_at",
)

# PostgreSQL derivation, lifted from the `roms_metadata` view (migration 0074)
# and extended with the denormalized rom columns (platform_id/regions/languages/
# tags) so facet queries never touch the wide `roms` table. The
# `/*WHERE_CLAUSE*/` sentinel scopes the inner scan to a set of rom ids when
# refreshing a subset.
_PG_ROMS_METADATA_SELECT = """
    SELECT
        r.id AS rom_id,
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
                THEN jsonb_path_query_array(r.igdb_metadata, '$.age_ratings[*].rating')
                ELSE NULL
            END,
            CASE
                WHEN r.ss_metadata IS NOT NULL
                    AND r.ss_metadata ? 'age_ratings'
                    AND jsonb_array_length(r.ss_metadata -> 'age_ratings') > 0
                THEN jsonb_path_query_array(r.ss_metadata, '$.age_ratings[*].rating')
                ELSE NULL
            END,
            CASE
                WHEN r.launchbox_metadata IS NOT NULL
                    AND r.launchbox_metadata ? 'esrb'
                    AND r.launchbox_metadata ->> 'esrb' IS NOT NULL
                    AND r.launchbox_metadata ->> 'esrb' != ''
                THEN jsonb_build_array(r.launchbox_metadata ->> 'esrb')
                ELSE NULL
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
            WHEN r.gamelist_metadata IS NOT NULL
                AND r.gamelist_metadata ? 'first_release_date'
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
        ) AS player_count,
        r.platform_id AS platform_id,
        r.regions AS regions,
        r.languages AS languages,
        r.tags AS tags,
        NOW() AS created_at,
        NOW() AS updated_at
    FROM (
        SELECT
            r.id,
            r.platform_id,
            r.regions,
            r.languages,
            r.tags,
            r.manual_metadata,
            r.igdb_metadata,
            r.moby_metadata,
            r.ss_metadata,
            r.ra_metadata,
            r.launchbox_metadata,
            r.flashpoint_metadata,
            r.gamelist_metadata,
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
            END AS launchbox_rating,
            CASE
                WHEN r.gamelist_metadata IS NOT NULL AND r.gamelist_metadata ? 'rating' AND
                    r.gamelist_metadata ->> 'rating' NOT IN ('null', 'None', '0', '0.0') AND
                    r.gamelist_metadata ->> 'rating' ~ '^[0-9]+(\\.[0-9]+)?$'
                THEN (r.gamelist_metadata ->> 'rating')::float * 100
                ELSE NULL
            END AS gamelist_rating
        FROM roms r/*WHERE_CLAUSE*/
    ) AS r
"""

# MariaDB / MySQL derivation, lifted from the `roms_metadata` view (migration
# 0074) and extended with the denormalized rom columns.
_MYSQL_ROMS_METADATA_SELECT = """
    SELECT
        r.id AS rom_id,
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
                THEN IF(
                    JSON_TYPE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                    JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating'),
                    JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.age_ratings[*].rating')))
                )
                ELSE NULL
            END,
            CASE
                WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.age_ratings')
                    AND JSON_LENGTH(JSON_EXTRACT(r.ss_metadata, '$.age_ratings')) > 0
                THEN IF(
                    JSON_TYPE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')) = 'ARRAY',
                    JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating'),
                    JSON_ARRAY(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.age_ratings[*].rating')))
                )
                ELSE NULL
            END,
            CASE
                WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.esrb')
                    AND JSON_EXTRACT(r.launchbox_metadata, '$.esrb') IS NOT NULL
                    AND JSON_EXTRACT(r.launchbox_metadata, '$.esrb') != ''
                THEN JSON_ARRAY(JSON_EXTRACT(r.launchbox_metadata, '$.esrb'))
                ELSE NULL
            END,
            JSON_ARRAY()
        ) AS age_ratings,
        CASE
            WHEN JSON_CONTAINS_PATH(r.manual_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.manual_metadata, '$.first_release_date')) AS SIGNED)
            WHEN JSON_CONTAINS_PATH(r.igdb_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.igdb_metadata, '$.first_release_date')) AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.ss_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.ss_metadata, '$.first_release_date')) AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.ra_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.ra_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.ra_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.ra_metadata, '$.first_release_date')) AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.launchbox_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.launchbox_metadata, '$.first_release_date')) AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.flashpoint_metadata, 'one', '$.first_release_date') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0') AND
                JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.first_release_date')) REGEXP '^[0-9]+$'
            THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(r.flashpoint_metadata, '$.first_release_date')) AS SIGNED) * 1000
            WHEN JSON_CONTAINS_PATH(r.gamelist_metadata, 'one', '$.first_release_date')
                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.first_release_date')) NOT IN ('null', 'None', '0', '0.0')
                AND JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.first_release_date')) REGEXP '^[0-9]{8}T[0-9]{6}$'
            THEN UNIX_TIMESTAMP(
                STR_TO_DATE(
                    JSON_UNQUOTE(JSON_EXTRACT(r.gamelist_metadata, '$.first_release_date')),
                    '%Y%m%dT%H%i%S'
                )
            ) * 1000
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
        ) AS player_count,
        r.platform_id AS platform_id,
        r.regions AS regions,
        r.languages AS languages,
        r.tags AS tags,
        NOW() AS created_at,
        NOW() AS updated_at
    FROM (
        SELECT
            id,
            platform_id,
            regions,
            languages,
            tags,
            manual_metadata,
            igdb_metadata,
            moby_metadata,
            ss_metadata,
            ra_metadata,
            launchbox_metadata,
            flashpoint_metadata,
            gamelist_metadata,
            CASE
                WHEN JSON_CONTAINS_PATH(igdb_metadata, 'one', '$.total_rating') AND
                    JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(igdb_metadata, '$.total_rating')) AS DECIMAL(10,2))
                ELSE NULL
            END AS igdb_rating,
            CASE
                WHEN JSON_CONTAINS_PATH(moby_metadata, 'one', '$.moby_score') AND
                    JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(moby_metadata, '$.moby_score')) AS DECIMAL(10,2)) * 10
                ELSE NULL
            END AS moby_rating,
            CASE
                WHEN JSON_CONTAINS_PATH(ss_metadata, 'one', '$.ss_score') AND
                    JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(ss_metadata, '$.ss_score')) AS DECIMAL(10,2)) * 10
                ELSE NULL
            END AS ss_rating,
            CASE
                WHEN JSON_CONTAINS_PATH(launchbox_metadata, 'one', '$.community_rating') AND
                    JSON_UNQUOTE(JSON_EXTRACT(launchbox_metadata, '$.community_rating')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(launchbox_metadata, '$.community_rating')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(launchbox_metadata, '$.community_rating')) AS DECIMAL(10,2)) * 20
                ELSE NULL
            END AS launchbox_rating,
            CASE
                WHEN JSON_CONTAINS_PATH(gamelist_metadata, 'one', '$.rating') AND
                    JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.rating')) NOT IN ('null', 'None', '0', '0.0') AND
                    JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.rating')) REGEXP '^[0-9]+(\\\\.[0-9]+)?$'
                THEN CAST(JSON_UNQUOTE(JSON_EXTRACT(gamelist_metadata, '$.rating')) AS DECIMAL(10,2)) * 100
                ELSE NULL
            END AS gamelist_rating
        FROM roms/*WHERE_CLAUSE*/
    ) AS r
"""

_ROMS_METADATA_INSERT_COLUMNS = (
    "rom_id",
    "genres",
    "franchises",
    "collections",
    "companies",
    "game_modes",
    "age_ratings",
    "first_release_date",
    "average_rating",
    "player_count",
    "platform_id",
    "regions",
    "languages",
    "tags",
    "created_at",
    "updated_at",
)

# virtual_collections aggregation, lifted from migrations 0095 (PostgreSQL) and
# 0096 (MariaDB/MySQL). Both read the materialized roms_metadata table.
_PG_VIRTUAL_COLLECTIONS_SELECT = """
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
        FROM roms r
        JOIN roms_metadata rm ON rm.rom_id = r.id
    ),
    genres_collection AS (
        SELECT rom_id, path_cover_s, path_cover_l,
            jsonb_array_elements_text(genres) as collection_name, 'genre' as collection_type
        FROM base
    ),
    franchises_collection AS (
        SELECT rom_id, path_cover_s, path_cover_l,
            jsonb_array_elements_text(franchises) as collection_name, 'franchise' as collection_type
        FROM base
    ),
    collection_collection AS (
        SELECT rom_id, path_cover_s, path_cover_l,
            jsonb_array_elements_text(collections) as collection_name, 'collection' as collection_type
        FROM base
    ),
    modes_collection AS (
        SELECT rom_id, path_cover_s, path_cover_l,
            jsonb_array_elements_text(game_modes) as collection_name, 'mode' as collection_type
        FROM base
    ),
    companies_collection AS (
        SELECT rom_id, path_cover_s, path_cover_l,
            jsonb_array_elements_text(companies) as collection_name, 'company' as collection_type
        FROM base
    )
    SELECT
        collection_name as name,
        collection_type as type,
        'Autogenerated ' || collection_type || ' collection' AS description,
        NOW() AS created_at,
        NOW() AS updated_at,
        jsonb_agg(rom_id) as rom_ids,
        jsonb_agg(path_cover_s) as path_covers_s,
        jsonb_agg(path_cover_l) as path_covers_l
    FROM (
        SELECT * FROM genres_collection
        UNION ALL SELECT * FROM franchises_collection
        UNION ALL SELECT * FROM collection_collection
        UNION ALL SELECT * FROM modes_collection
        UNION ALL SELECT * FROM companies_collection
    ) combined
    GROUP BY collection_type, collection_name
    HAVING COUNT(DISTINCT rom_id) > 2
"""

_MYSQL_VIRTUAL_COLLECTIONS_SELECT = """
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
        FROM roms r
        JOIN roms_metadata rm ON rm.rom_id = r.id
    ),
    genres AS (
        SELECT base.rom_id, base.path_cover_s, base.path_cover_l,
            CONCAT(j.genre) COLLATE utf8mb4_general_ci as collection_name,
            'genre' COLLATE utf8mb4_general_ci as collection_type
        FROM base CROSS JOIN JSON_TABLE(base.genres, '$[*]' COLUMNS (genre VARCHAR(255) PATH '$')) j
    ),
    franchises AS (
        SELECT base.rom_id, base.path_cover_s, base.path_cover_l,
            CONCAT(j.franchise) COLLATE utf8mb4_general_ci as collection_name,
            'franchise' COLLATE utf8mb4_general_ci as collection_type
        FROM base CROSS JOIN JSON_TABLE(base.franchises, '$[*]' COLUMNS (franchise VARCHAR(255) PATH '$')) j
    ),
    collections AS (
        SELECT base.rom_id, base.path_cover_s, base.path_cover_l,
            CONCAT(j.collection) COLLATE utf8mb4_general_ci as collection_name,
            'collection' COLLATE utf8mb4_general_ci as collection_type
        FROM base CROSS JOIN JSON_TABLE(base.collections, '$[*]' COLUMNS (collection VARCHAR(255) PATH '$')) j
    ),
    modes AS (
        SELECT base.rom_id, base.path_cover_s, base.path_cover_l,
            CONCAT(j.mode) COLLATE utf8mb4_general_ci as collection_name,
            'mode' COLLATE utf8mb4_general_ci as collection_type
        FROM base CROSS JOIN JSON_TABLE(base.game_modes, '$[*]' COLUMNS (mode VARCHAR(255) PATH '$')) j
    ),
    companies AS (
        SELECT base.rom_id, base.path_cover_s, base.path_cover_l,
            CONCAT(j.company) COLLATE utf8mb4_general_ci as collection_name,
            'company' COLLATE utf8mb4_general_ci as collection_type
        FROM base CROSS JOIN JSON_TABLE(base.companies, '$[*]' COLUMNS (company VARCHAR(255) PATH '$')) j
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
    FROM (
        SELECT * FROM genres
        UNION ALL SELECT * FROM franchises
        UNION ALL SELECT * FROM collections
        UNION ALL SELECT * FROM modes
        UNION ALL SELECT * FROM companies
    ) combined
    GROUP BY collection_type, collection_name
    HAVING COUNT(DISTINCT rom_id) > 2
"""

_VIRTUAL_COLLECTIONS_INSERT_COLUMNS = (
    "name",
    "type",
    "description",
    "created_at",
    "updated_at",
    "rom_ids",
    "path_covers_s",
    "path_covers_l",
)


def _build_roms_metadata_statement(is_pg: bool, scoped: bool) -> sa.TextClause:
    """Build the INSERT ... SELECT upsert for the roms_metadata table."""
    select_body = _PG_ROMS_METADATA_SELECT if is_pg else _MYSQL_ROMS_METADATA_SELECT
    if not scoped:
        where = ""
    elif is_pg:
        where = " WHERE r.id IN :rom_ids"
    else:
        where = " WHERE id IN :rom_ids"
    # A sentinel comment is used instead of str.format() because the SQL bodies
    # contain literal `{n}` regex quantifiers.
    select_sql = select_body.replace("/*WHERE_CLAUSE*/", where)

    insert_cols = ", ".join(_ROMS_METADATA_INSERT_COLUMNS)
    if is_pg:
        assignments = ", ".join(
            f"{col} = EXCLUDED.{col}" for col in _ROMS_METADATA_UPSERT_COLUMNS
        )
        conflict = f"ON CONFLICT (rom_id) DO UPDATE SET {assignments}"  # nosec B608
    else:
        assignments = ", ".join(
            f"{col} = VALUES({col})" for col in _ROMS_METADATA_UPSERT_COLUMNS
        )
        conflict = f"ON DUPLICATE KEY UPDATE {assignments}"

    sql = f"INSERT INTO roms_metadata ({insert_cols})\n{select_sql}\n{conflict}"  # nosec B608
    stmt = sa.text(sql)
    if scoped:
        stmt = stmt.bindparams(sa.bindparam("rom_ids", expanding=True))
    return stmt


def refresh_roms_metadata(
    session: Session,
    rom_ids: Sequence[int] | None = None,
) -> None:
    """Recompute the materialized roms_metadata rows.

    Passing ``rom_ids`` refreshes just those roms (used on the rom write
    paths); ``None`` rebuilds the whole table.
    """
    if rom_ids is not None and len(rom_ids) == 0:
        return

    is_pg = is_postgresql(session.get_bind())
    stmt = _build_roms_metadata_statement(is_pg=is_pg, scoped=rom_ids is not None)
    params = {"rom_ids": list(rom_ids)} if rom_ids is not None else {}
    session.execute(stmt, params)


def refresh_virtual_collections(session: Session) -> None:
    """Rebuild the whole materialized virtual_collections table.

    This is a full-library aggregation (GROUP BY over every rom's facets with a
    ``> 2`` membership threshold), so it can only be rebuilt in full. Runs as a
    delete + repopulate inside the caller's transaction.
    """
    is_pg = is_postgresql(session.get_bind())
    select_body = (
        _PG_VIRTUAL_COLLECTIONS_SELECT if is_pg else _MYSQL_VIRTUAL_COLLECTIONS_SELECT
    )
    insert_cols = ", ".join(_VIRTUAL_COLLECTIONS_INSERT_COLUMNS)

    session.execute(sa.text("DELETE FROM virtual_collections"))
    session.execute(
        sa.text(
            f"INSERT INTO virtual_collections ({insert_cols})\n{select_body}"
        )  # nosec B608
    )
