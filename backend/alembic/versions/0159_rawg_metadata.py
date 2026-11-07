"""Add RAWG match id and metadata

Revision ID: 0159_rawg_metadata
Revises: 0158_platform_first_release_year
Create Date: 2026-11-03 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import MIN_AGE_COLUMN, is_postgresql
from utils.roms_columns import TAG_COLUMNS, ensure_roms_columns

revision = "0159_rawg_metadata"
down_revision = "0158_platform_first_release_year"
branch_labels = None
depends_on = None


# 0148's mirrored list, which this revision appends to.
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
    ("steam_id", "steam_id"),
] + [(facet, generated) for generated, facet in TAG_COLUMNS]
_MIRRORED_COLUMNS_BEFORE.append((MIN_AGE_COLUMN, MIN_AGE_COLUMN))
_MIRRORED_COLUMNS_AFTER = _MIRRORED_COLUMNS_BEFORE + [("rawg_id", "rawg_id")]

_MYSQL_TRIGGERS = {
    "roms_facets_after_insert": "AFTER INSERT",
    "roms_facets_after_update": "AFTER UPDATE",
}


def _rebuild_triggers(pg: bool, mirrored: list[tuple[str, str]]) -> None:
    """Recreate the roms_facets sync triggers over the given column list."""
    targets = ", ".join(target for target, _ in mirrored)
    values = ", ".join(f"NEW.{source}" for _, source in mirrored)

    if pg:
        assignments = ", ".join(
            f"{target} = EXCLUDED.{target}" for target, _ in mirrored
        )
        op.execute(f"""
CREATE OR REPLACE FUNCTION romm_sync_rom_facets() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO roms_facets (rom_id, {targets})
    VALUES (NEW.id, {values})
    ON CONFLICT (rom_id) DO UPDATE SET
        {assignments},
        updated_at = NOW();
    RETURN NULL;
END $$
""")  # nosec B608
        return

    updates = ",\n".join(f"{target} = VALUES({target})" for target, _ in mirrored)
    body = (
        f"INSERT INTO roms_facets (rom_id, {targets})\n"  # nosec B608
        f"VALUES (NEW.id, {values})\n"
        f"ON DUPLICATE KEY UPDATE\n{updates},\nupdated_at = CURRENT_TIMESTAMP"
    )
    for name, timing in _MYSQL_TRIGGERS.items():
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
        op.execute(f"CREATE TRIGGER {name} {timing} ON roms\nFOR EACH ROW\n{body}")


def upgrade() -> None:
    ensure_roms_columns(op.get_bind())
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            "idx_roms_rawg_id", ["rawg_id"], unique=False, if_not_exists=True
        )

    op.add_column(
        "roms_facets",
        sa.Column("rawg_id", sa.Integer(), nullable=True),
        if_not_exists=True,
    )

    _rebuild_triggers(is_postgresql(op.get_bind()), _MIRRORED_COLUMNS_AFTER)


def downgrade() -> None:
    _rebuild_triggers(is_postgresql(op.get_bind()), _MIRRORED_COLUMNS_BEFORE)
    op.drop_column("roms_facets", "rawg_id", if_exists=True)

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_rawg_id", if_exists=True)
        batch_op.drop_column("rawg_metadata", if_exists=True)
        batch_op.drop_column("rawg_id", if_exists=True)
