"""Add Steam match id and metadata

Revision ID: 0115_add_steam_metadata
Revises: 0114_demozoo_pouet_csdb_metadata
Create Date: 2026-08-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0115_add_steam_metadata"
down_revision = "0114_demozoo_pouet_csdb_metadata"
branch_labels = None
depends_on = None


# (roms_facets column, roms source column) pairs the triggers keep in sync.
# Must match migration 0114's final list, which this revision appends to.
_MIRRORED_COLUMNS_BEFORE = [
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
    ("igdb_id", "igdb_id"),
    ("ss_id", "ss_id"),
    ("moby_id", "moby_id"),
    ("launchbox_id", "launchbox_id"),
    ("ra_id", "ra_id"),
    ("hasheous_id", "hasheous_id"),
    ("tgdb_id", "tgdb_id"),
    ("flashpoint_id", "flashpoint_id"),
    ("hltb_id", "hltb_id"),
    ("demozoo_id", "demozoo_id"),
    ("pouet_id", "pouet_id"),
    ("csdb_id", "csdb_id"),
    ("gamelist_id", "gamelist_id"),
    ("libretro_id", "libretro_id"),
]
_MIRRORED_COLUMNS_AFTER = _MIRRORED_COLUMNS_BEFORE + [("steam_id", "steam_id")]

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


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("steam_id", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column(
                "steam_metadata",
                sa.JSON().with_variant(
                    postgresql.JSONB(astext_type=sa.Text()), "postgresql"
                ),
                nullable=True,
            ),
            if_not_exists=True,
        )
        batch_op.create_index(
            "idx_roms_steam_id", ["steam_id"], unique=False, if_not_exists=True
        )

    # MySQL/MariaDB auto-commit each DDL, so a crash here can leave the column
    # behind without advancing the alembic version.
    existing = {
        col["name"] for col in inspect(op.get_bind()).get_columns("roms_facets")
    }
    if "steam_id" not in existing:
        op.add_column("roms_facets", sa.Column("steam_id", sa.Integer(), nullable=True))

    _recreate_triggers(_MIRRORED_COLUMNS_AFTER)


def downgrade() -> None:
    _recreate_triggers(_MIRRORED_COLUMNS_BEFORE)
    op.drop_column("roms_facets", "steam_id", if_exists=True)

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_steam_id", if_exists=True)
        batch_op.drop_column("steam_metadata", if_exists=True)
        batch_op.drop_column("steam_id", if_exists=True)
