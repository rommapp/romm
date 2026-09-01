"""Add Demozoo / Pouët / CSDb match ids and metadata

Revision ID: 0114_demozoo_pouet_csdb_metadata
Revises: 0113_roms_locked_fields
Create Date: 2026-08-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0114_demozoo_pouet_csdb_metadata"
down_revision = "0113_roms_locked_fields"
branch_labels = None
depends_on = None

_NEW_ROMS_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("demozoo_id", sa.Integer()),
    ("pouet_id", sa.Integer()),
    ("csdb_id", sa.Integer()),
]
_NEW_METADATA_COLUMNS = ["demozoo_metadata", "pouet_metadata", "csdb_metadata"]

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

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
    ("publishers", "generated_publishers"),
    ("developers", "generated_developers"),
]
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
    ("demozoo_id", sa.Integer()),
    ("pouet_id", sa.Integer()),
    ("csdb_id", sa.Integer()),
    ("gamelist_id", sa.String(length=100)),
    ("libretro_id", sa.String(length=64)),
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
    if is_postgresql(op.get_bind()):
        op.execute(_postgres_sync_fn(mirrored_columns))
    else:
        body = _mysql_upsert_body(mirrored_columns)
        for name, timing in _MYSQL_TRIGGERS.items():
            op.execute(f"DROP TRIGGER IF EXISTS {name}")
            op.execute(f"CREATE TRIGGER {name} {timing} ON roms\nFOR EACH ROW\n{body}")


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        for name, column_type in _NEW_ROMS_COLUMNS:
            batch_op.add_column(
                sa.Column(name, column_type, nullable=True), if_not_exists=True
            )
        for name in _NEW_METADATA_COLUMNS:
            batch_op.add_column(
                sa.Column(name, _JSON, nullable=True), if_not_exists=True
            )
        for name, _ in _NEW_ROMS_COLUMNS:
            batch_op.create_index(
                f"idx_roms_{name}", [name], unique=False, if_not_exists=True
            )

    existing = {
        col["name"] for col in inspect(op.get_bind()).get_columns("roms_facets")
    }
    for name, column_type in _NEW_ROMS_COLUMNS:
        if name not in existing:
            op.add_column("roms_facets", sa.Column(name, column_type, nullable=True))

    _recreate_triggers(_FULL_MIRRORED_COLUMNS)


def downgrade() -> None:
    added = {name for name, _ in _NEW_ROMS_COLUMNS}
    _recreate_triggers(
        [pair for pair in _FULL_MIRRORED_COLUMNS if pair[0] not in added]
    )
    for name, _ in _NEW_ROMS_COLUMNS:
        op.drop_column("roms_facets", name)
    with op.batch_alter_table("roms", schema=None) as batch_op:
        for name, _ in reversed(_NEW_ROMS_COLUMNS):
            batch_op.drop_index(f"idx_roms_{name}", if_exists=True)
        for name in reversed(_NEW_METADATA_COLUMNS):
            batch_op.drop_column(name, if_exists=True)
        for name, _ in reversed(_NEW_ROMS_COLUMNS):
            batch_op.drop_column(name, if_exists=True)
