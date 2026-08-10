"""Expose IGDB's rating count so a rating can be weighted by its confidence

`average_rating` averages whatever providers rated a game, which makes a
single ScreenScraper 10/10 indistinguishable from a broad consensus. On a real
15k library sixteen games score a perfect 100, every one of them with no IGDB
votes behind it -- and the cold-start feed, which orders by rating alone,
recommended all sixteen alphabetically.

Storing IGDB's vote count lets that feed shrink a rating toward the library
mean in proportion to how little evidence backs it.

Only IGDB reports a count, and `manual_metadata` can override it like every
other generated facet.

Revision ID: 0110_rating_count_column
Revises: 0109_igdb_tag_columns
Create Date: 2026-08-08 00:00:00.000000

"""

from alembic import op  # type: ignore[attr-defined]

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0110_rating_count_column"
down_revision = "0109_igdb_tag_columns"
branch_labels = None
depends_on = None

_COLUMN = "generated_rating_count"
_SOURCES = ["manual_metadata", "igdb_metadata"]

# Restated in full because CREATE OR REPLACE VIEW rewrites every projection.
_VIEW_COLUMNS = [
    ("generated_genres", "genres"),
    ("generated_franchises", "franchises"),
    ("generated_collections", "collections"),
    ("generated_companies", "companies"),
    ("generated_game_modes", "game_modes"),
    ("generated_age_ratings", "age_ratings"),
    ("generated_keywords", "keywords"),
    ("generated_themes", "themes"),
    ("generated_player_perspectives", "player_perspectives"),
    ("generated_first_release_date", "first_release_date"),
    ("generated_average_rating", "average_rating"),
    ("generated_player_count", "player_count"),
]


def _maria_expr() -> str:
    branches = [
        f"NULLIF(JSON_VALUE({src}, '$.total_rating_count'), '')" for src in _SOURCES
    ]
    return "CAST(COALESCE(" + ", ".join(branches) + ", 0) AS SIGNED)"


def _postgres_expr() -> str:
    branches = [f"({src} ->> 'total_rating_count')" for src in _SOURCES]
    return (
        "COALESCE("
        + ", ".join(f"NULLIF({b}, '')::numeric" for b in branches)
        + ", 0)::bigint"
    )


def _view_sql(is_pg: bool, columns: list[tuple[str, str]]) -> str:
    projections = ",\n    ".join(
        # The view exposed player_count as text and PostgreSQL cannot change a
        # column's type through CREATE OR REPLACE VIEW.
        (
            f"{name}::text AS {alias}"
            if is_pg and alias == "player_count"
            else f"{name} AS {alias}"
        )
        for name, alias in columns
    )
    return (
        "CREATE OR REPLACE VIEW roms_metadata AS\n"  # nosec B608
        "SELECT\n"
        "    id AS rom_id,\n"
        "    NOW() AS created_at,\n"
        "    NOW() AS updated_at,\n"
        f"    {projections}\n"
        "FROM roms"
    )


def upgrade() -> None:
    is_pg = is_postgresql(op.get_bind())
    expr = _postgres_expr() if is_pg else _maria_expr()
    column_type = "BIGINT" if is_pg else "BIGINT"

    op.execute(
        f"ALTER TABLE roms ADD COLUMN {_COLUMN} {column_type} "  # nosec B608
        f"GENERATED ALWAYS AS ({expr}) STORED"
    )
    op.execute(_view_sql(is_pg, _VIEW_COLUMNS + [(_COLUMN, "rating_count")]))


def downgrade() -> None:
    is_pg = is_postgresql(op.get_bind())

    # The view has to stop referencing the column before it can be dropped.
    op.execute("DROP VIEW IF EXISTS roms_metadata")
    op.execute(_view_sql(is_pg, _VIEW_COLUMNS).replace("CREATE OR REPLACE", "CREATE"))
    op.execute(f"ALTER TABLE roms DROP COLUMN {_COLUMN}")
