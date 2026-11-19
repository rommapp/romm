"""MAME index as a metadata source: match id, metadata, filter facets and grouping

`roms.mame_id` holds the parent set's short name, so a parent and its clones
share it and become siblings through `rom_identity_keys` (provider 9). The set
facts the gallery filters on are generated from `mame_metadata` and mirrored
into `roms_facets`, and the genre, company and release date chains read MAME
after every other provider.

Revision ID: 0162_mame_metadata
Revises: 0161_save_channels
Create Date: 2026-11-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import column_names, is_postgresql
from utils.roms_columns import (
    ROMS_METADATA_VIEW_COLUMNS,
    TAG_COLUMNS,
    ensure_roms_columns,
    mame_unfed_columns,
    rebuild_generated_columns,
)

# revision identifiers, used by Alembic.
revision = "0162_mame_metadata"
down_revision = "0161_save_channels"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# roms_facets mirror
# ---------------------------------------------------------------------------

# 0148's final list, which this revision appends to.
_FACETS_BEFORE = (
    [
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
    ]
    + [(facet, generated) for generated, facet in TAG_COLUMNS]
    + [("min_age", "min_age")]
)


def _facet_columns() -> list[sa.Column]:
    # Fresh objects per call: a Column binds to the first table it joins.
    return [
        sa.Column("mame_id", sa.String(length=100), nullable=True),
        sa.Column("mame_set_type", sa.String(length=16), nullable=True),
        sa.Column("mame_status", sa.String(length=16), nullable=True),
        sa.Column("mame_driver", sa.String(length=100), nullable=True),
        sa.Column("mame_mechanical", sa.Boolean(), nullable=True),
    ]


_FACETS_AFTER = _FACETS_BEFORE + [
    ("mame_id", "mame_id"),
    ("mame_set_type", "generated_mame_set_type"),
    ("mame_status", "generated_mame_status"),
    ("mame_driver", "generated_mame_driver"),
    ("mame_mechanical", "generated_mame_mechanical"),
]

_MYSQL_FACET_TRIGGERS = {
    "roms_facets_after_insert": "AFTER INSERT",
    "roms_facets_after_update": "AFTER UPDATE",
}


def _rebuild_facet_triggers(pg: bool, mirrored: list[tuple[str, str]]) -> None:
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
    for name, timing in _MYSQL_FACET_TRIGGERS.items():
        op.execute(f"DROP TRIGGER IF EXISTS {name}")
        op.execute(f"CREATE TRIGGER {name} {timing} ON roms\nFOR EACH ROW\n{body}")


# ---------------------------------------------------------------------------
# rom_identity_keys triggers (0127's, with MAME appended)
# ---------------------------------------------------------------------------

KEYS_TABLE = "rom_identity_keys"
_KEY_COLUMNS = "provider, platform_id, provider_id, rom_id"

# A frozen snapshot of `IDENTITY_ID_FIELDS` and its positions.
_PROVIDERS_BEFORE = (
    (0, "igdb_id"),
    (1, "moby_id"),
    (2, "ss_id"),
    (3, "launchbox_id"),
    (4, "ra_id"),
    (5, "hasheous_id"),
    (6, "tgdb_id"),
    (7, "steam_id"),
    (8, "flashpoint_id"),
)
_PROVIDERS_AFTER = _PROVIDERS_BEFORE + ((9, "mame_id"),)


def _as_provider_id(pg: bool, expression: str) -> str:
    return f"CAST({expression} AS {'VARCHAR' if pg else 'CHAR'})"


def _mysql_identity_triggers(providers: tuple[tuple[int, str], ...]) -> list[str]:
    tracked = ["platform_id"] + [column for _, column in providers]
    unchanged = " AND ".join(f"NEW.{c} <=> OLD.{c}" for c in tracked)
    inserts = "\n".join(
        f"IF NEW.{column} IS NOT NULL THEN\n"  # nosec B608
        f"INSERT IGNORE INTO {KEYS_TABLE} ({_KEY_COLUMNS}) "
        f"VALUES ({code}, NEW.platform_id, "
        f"{_as_provider_id(False, f'NEW.{column}')}, NEW.id);\n"
        "END IF;"
        for code, column in providers
    )
    return [
        f"CREATE TRIGGER {KEYS_TABLE}_ai AFTER INSERT ON roms\n"
        f"FOR EACH ROW\nBEGIN\n{inserts}\nEND",
        f"CREATE TRIGGER {KEYS_TABLE}_au AFTER UPDATE ON roms\n"  # nosec B608
        f"FOR EACH ROW\nBEGIN\n"
        f"IF NOT ({unchanged}) THEN\n"
        f"DELETE FROM {KEYS_TABLE} WHERE rom_id = NEW.id;\n"
        f"{inserts}\n"
        f"END IF;\n"
        f"END",
    ]


def _postgres_identity_function(providers: tuple[tuple[int, str], ...]) -> str:
    tracked = ["platform_id"] + [column for _, column in providers]
    unchanged = " AND ".join(f"NEW.{c} IS NOT DISTINCT FROM OLD.{c}" for c in tracked)
    inserts = "\n".join(
        f"    IF NEW.{column} IS NOT NULL THEN\n"  # nosec B608
        f"        INSERT INTO {KEYS_TABLE} ({_KEY_COLUMNS})\n"
        f"        VALUES ({code}, NEW.platform_id, "
        f"{_as_provider_id(True, f'NEW.{column}')}, NEW.id)\n"
        f"        ON CONFLICT DO NOTHING;\n"
        f"    END IF;"
        for code, column in providers
    )
    return f"""
CREATE OR REPLACE FUNCTION romm_sync_rom_identity_keys() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF {unchanged} THEN
            RETURN NULL;
        END IF;
        DELETE FROM {KEYS_TABLE} WHERE rom_id = NEW.id;
    END IF;

{inserts}

    RETURN NULL;
END $$
"""  # nosec B608


def _rebuild_identity_triggers(
    pg: bool, providers: tuple[tuple[int, str], ...]
) -> None:
    if pg:
        # The trigger itself is unchanged; only the function body it calls.
        op.execute(_postgres_identity_function(providers))
        return
    op.execute(f"DROP TRIGGER IF EXISTS {KEYS_TABLE}_ai")
    op.execute(f"DROP TRIGGER IF EXISTS {KEYS_TABLE}_au")
    for trigger in _mysql_identity_triggers(providers):
        op.execute(trigger)


def _backfill_mame_keys(pg: bool) -> None:
    select = (
        f"SELECT 9, platform_id, {_as_provider_id(pg, 'mame_id')}, id "  # nosec B608
        "FROM roms WHERE mame_id IS NOT NULL"
    )
    if pg:
        op.execute(
            f"INSERT INTO {KEYS_TABLE} ({_KEY_COLUMNS})\n{select}\nON CONFLICT DO NOTHING"  # nosec B608
        )
    else:
        op.execute(
            f"INSERT IGNORE INTO {KEYS_TABLE} ({_KEY_COLUMNS})\n{select}"
        )  # nosec B608


# ---------------------------------------------------------------------------
# Dedup window cover (0127's, with mame_id)
# ---------------------------------------------------------------------------

COVER_INDEX = "idx_roms_sibling_cover"
_COVER_HEAD = [
    "platform_id",
    "igdb_id",
    "moby_id",
    "ss_id",
    "launchbox_id",
    "ra_id",
    "hasheous_id",
    "tgdb_id",
    "flashpoint_id",
    "steam_id",
]
_COVER_TAIL = ["fs_name_no_ext", "generated_primary_region", "id"]
OLD_COVER_COLUMNS = [*_COVER_HEAD, *_COVER_TAIL]
NEW_COVER_COLUMNS = [*_COVER_HEAD, "mame_id", *_COVER_TAIL]


def _rebuild_cover_index(columns: list[str]) -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index(COVER_INDEX, if_exists=True)
        batch_op.create_index(COVER_INDEX, columns, unique=False, if_not_exists=True)


def upgrade() -> None:
    conn = op.get_bind()
    pg = is_postgresql(conn)

    ensure_roms_columns(conn)
    unfed = mame_unfed_columns(conn)
    if unfed:
        rebuild_generated_columns(
            conn, add=unfed, drop=[], view_columns=ROMS_METADATA_VIEW_COLUMNS
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            "idx_roms_mame_id", ["mame_id"], unique=False, if_not_exists=True
        )

    present = column_names(conn, "roms_facets")
    for column in _facet_columns():
        if column.name not in present:
            op.add_column("roms_facets", column)
    _rebuild_facet_triggers(pg, _FACETS_AFTER)

    _rebuild_identity_triggers(pg, _PROVIDERS_AFTER)
    _backfill_mame_keys(pg)
    _rebuild_cover_index(NEW_COVER_COLUMNS)


def downgrade() -> None:
    conn = op.get_bind()
    pg = is_postgresql(conn)

    _rebuild_cover_index(OLD_COVER_COLUMNS)
    _rebuild_identity_triggers(pg, _PROVIDERS_BEFORE)
    op.execute(f"DELETE FROM {KEYS_TABLE} WHERE provider = 9")  # nosec B608

    _rebuild_facet_triggers(pg, _FACETS_BEFORE)
    present = column_names(conn, "roms_facets")
    for column in _facet_columns():
        if column.name in present:
            op.drop_column("roms_facets", column.name)

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_mame_id", if_exists=True)
    # The MAME columns stay: they belong to the 0108 catalog, whose downgrade
    # removes them with the rest.
