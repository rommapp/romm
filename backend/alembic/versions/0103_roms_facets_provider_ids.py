"""Mirror the provider match ids into ``roms_facets``

The Server Stats metadata-coverage breakdown counts the eleven provider-id
columns per platform. Those columns live inline on ``roms`` next to the raw
provider-metadata blobs, and four of them (``flashpoint_id``, ``hltb_id``,
``gamelist_id``, ``libretro_id``) are not part of any composite index with
``platform_id``, so the count fell back to a full scan of the multi-gigabyte
``roms`` table on every visit to the page.

This extends the narrow ``roms_facets`` mirror (migration 0100) with those ids
so the breakdown aggregates a few MB of data indexed by ``platform_id`` instead.
The mirror stays trigger-maintained, so the triggers are recreated with the
wider column set.

Revision ID: 0103_roms_facets_provider_ids
Revises: 0102_music_playlists
Create Date: 2026-07-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy import inspect

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0103_roms_facets_provider_ids"
down_revision = "0102_music_playlists"
branch_labels = None
depends_on = None


# New (roms_facets column, type) pairs. The source column on `roms` has the
# same name, so the trigger mirrors NEW.<name> straight across.
_PROVIDER_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("igdb_id", sa.Integer()),
    ("ss_id", sa.Integer()),
    ("moby_id", sa.Integer()),
    ("launchbox_id", sa.Integer()),
    ("ra_id", sa.Integer()),
    ("hasheous_id", sa.Integer()),
    ("tgdb_id", sa.Integer()),
    ("flashpoint_id", sa.String(length=100)),
    ("hltb_id", sa.Integer()),
    ("gamelist_id", sa.String(length=100)),
    ("libretro_id", sa.String(length=64)),
]

# (roms_facets column, roms source column) pairs the triggers keep in sync.
# Mirrors migration 0100's list; the provider ids are appended here.
_BASE_MIRRORED_COLUMNS = [
    ("platform_id", "platform_id"),
    ("genres", "generated_genres"),
    ("franchises", "generated_franchises"),
    ("collections", "generated_collections"),
    ("companies", "generated_companies"),
    ("game_modes", "generated_game_modes"),
    ("age_ratings", "generated_age_ratings"),
    ("player_count", "generated_player_count"),
    ("regions", "regions"),
    ("languages", "languages"),
    ("tags", "tags"),
]
_PROVIDER_MIRRORED_COLUMNS = [(name, name) for name, _ in _PROVIDER_COLUMNS]
_FULL_MIRRORED_COLUMNS = _BASE_MIRRORED_COLUMNS + _PROVIDER_MIRRORED_COLUMNS

_MYSQL_TRIGGERS = {
    "roms_facets_after_insert": "AFTER INSERT",
    "roms_facets_after_update": "AFTER UPDATE",
}


def _mysql_upsert_body(mirrored_columns: list[tuple[str, str]]) -> str:
    targets = ", ".join(target for target, _ in mirrored_columns)
    values = ", ".join(f"NEW.{source}" for _, source in mirrored_columns)
    updates = ",\n".join(
        f"{target} = VALUES({target})" for target, _ in mirrored_columns
    )
    return (
        f"INSERT INTO roms_facets (rom_id, {targets})\n"  # nosec B608
        f"VALUES (NEW.id, {values})\n"
        f"ON DUPLICATE KEY UPDATE\n{updates},\n"
        "updated_at = CURRENT_TIMESTAMP"
    )


def _postgres_sync_fn(mirrored_columns: list[tuple[str, str]]) -> str:
    targets = ", ".join(target for target, _ in mirrored_columns)
    values = ", ".join(f"NEW.{source}" for _, source in mirrored_columns)
    updates = ", ".join(
        f"{target} = EXCLUDED.{target}" for target, _ in mirrored_columns
    )
    return f"""
CREATE OR REPLACE FUNCTION romm_sync_rom_facets() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO roms_facets (rom_id, {targets})
    VALUES (NEW.id, {values})
    ON CONFLICT (rom_id) DO UPDATE SET
        {updates},
        updated_at = NOW();
    RETURN NULL;
END $$
"""  # nosec B608


def _recreate_triggers(mirrored_columns: list[tuple[str, str]]) -> None:
    """Rebuild the facet-sync triggers to cover `mirrored_columns`."""
    if is_postgresql(op.get_bind()):
        # The trigger itself is unchanged; only the function body it calls.
        op.execute(_postgres_sync_fn(mirrored_columns))
    else:
        body = _mysql_upsert_body(mirrored_columns)
        for name, timing in _MYSQL_TRIGGERS.items():
            op.execute(f"DROP TRIGGER IF EXISTS {name}")
            op.execute(f"CREATE TRIGGER {name} {timing} ON roms\nFOR EACH ROW\n{body}")


def _backfill_sql() -> str:
    if is_postgresql(op.get_bind()):
        # Postgres forbids qualifying the SET target with the table alias.
        assignments = ", ".join(f"{name} = r.{name}" for name, _ in _PROVIDER_COLUMNS)
        return (
            f"UPDATE roms_facets AS f SET {assignments} "  # nosec B608
            "FROM roms AS r WHERE f.rom_id = r.id"
        )
    # MySQL/MariaDB needs the target qualified; both tables share the names.
    assignments = ", ".join(f"f.{name} = r.{name}" for name, _ in _PROVIDER_COLUMNS)
    return (
        "UPDATE roms_facets AS f "  # nosec B608
        f"JOIN roms AS r ON f.rom_id = r.id SET {assignments}"
    )


def upgrade() -> None:
    # Guarded so a re-run after a partial failure skips columns already added.
    # MySQL/MariaDB auto-commit each DDL, so a mid-migration crash can leave a
    # subset of the columns behind without advancing the alembic version.
    existing = {
        col["name"] for col in inspect(op.get_bind()).get_columns("roms_facets")
    }
    for name, column_type in _PROVIDER_COLUMNS:
        if name not in existing:
            op.add_column("roms_facets", sa.Column(name, column_type, nullable=True))

    op.execute(_backfill_sql())
    _recreate_triggers(_FULL_MIRRORED_COLUMNS)


def downgrade() -> None:
    _recreate_triggers(_BASE_MIRRORED_COLUMNS)
    for name, _ in _PROVIDER_COLUMNS:
        op.drop_column("roms_facets", name)
