"""Materialize the ids `sibling_roms` matches on into an indexed table

``sibling_roms`` was a view that self-joined ``roms`` on an OR of seven
equalities across seven columns. The compared values come from the joined row,
so no index can drive that OR: MariaDB answers it by block-nested-loop scanning
every ROM on the page's platform. That made every gallery page pay for the
sibling badges (~54% of a 1s request on an 18.5k-ROM library), and the gallery's
"Versions" filter, which asks the same view for an EXISTS over the whole
library, a four-minute request.

The ids now live in ``rom_identity_keys``, one narrow row per (ROM, provider it
matched), and the view is a self-join of that table on (provider, platform,
provider id). The table is kept in sync by triggers on ``roms`` (no application
hook, no background job), with rom deletions handled by the foreign key's
cascade.

Notes:
- Storing the ids rather than the pairs keeps this linear in the library. A
  materialized pair table reads marginally faster but grows as the square of a
  sibling group, and its trigger has to read other ROMs, so a single mis-scrape
  pointing 800 ROMs at one game would write 642k rows.
- The view emits one row per matching provider, so a pair matched by both IGDB
  and ScreenScraper appears twice. `DISTINCT` would collapse that at 11x the
  cost, because it stops the view merging into the caller's query; the two
  readers dedupe instead.
- Matching is unchanged: the same seven providers, still scoped to a platform,
  so responses are identical. `steam_id` (in `IDENTITY_ID_FIELDS`) and
  `flashpoint_id` (in the `group_by_meta_id` window) are still not part of it.

Revision ID: 0127_rom_identity_keys
Revises: 0126_unique_rom_full_path
Create Date: 2026-09-07 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0127_rom_identity_keys"
down_revision = "0126_unique_rom_full_path"
branch_labels = None
depends_on = None


TABLE = "rom_identity_keys"

# (provider code, roms column). Frozen here rather than read off
# `SIBLING_IDENTITY_ID_FIELDS`, which a later migration is free to extend.
IDENTITY_PROVIDERS = (
    (0, "igdb_id"),
    (1, "moby_id"),
    (2, "ss_id"),
    (3, "launchbox_id"),
    (4, "ra_id"),
    (5, "hasheous_id"),
    (6, "tgdb_id"),
)

_COLUMNS = "provider, platform_id, provider_id, rom_id"

# A change to any of these invalidates the ROM's key rows.
_TRACKED_COLUMNS = ["platform_id"] + [column for _, column in IDENTITY_PROVIDERS]


# ---------------------------------------------------------------------------
# Backfill and triggers
# ---------------------------------------------------------------------------


def _backfill(pg: bool) -> list[str]:
    """One statement per provider, skipping the ROMs it never matched.

    Insert-or-skip, so a re-run after a partial failure only fills the rows
    still missing, and the rows the triggers already wrote are left alone.
    """
    statements = []
    for code, column in IDENTITY_PROVIDERS:
        select = (
            f"SELECT {code}, platform_id, {column}, id "  # nosec B608
            f"FROM roms WHERE {column} IS NOT NULL"
        )
        if pg:
            statements.append(
                f"INSERT INTO {TABLE} ({_COLUMNS})\n{select}\nON CONFLICT DO NOTHING"  # nosec B608
            )
        else:
            statements.append(
                f"INSERT IGNORE INTO {TABLE} ({_COLUMNS})\n{select}"
            )  # nosec B608
    return statements


def _mysql_inserts() -> str:
    """A ROM's key rows, one guarded statement per provider.

    MySQL/MariaDB do not expose ``NEW.*`` inside a derived table in a trigger
    body, so the NULLs cannot be filtered out by a single INSERT ... SELECT.
    """
    return "\n".join(
        f"IF NEW.{column} IS NOT NULL THEN\n"  # nosec B608
        f"INSERT IGNORE INTO {TABLE} ({_COLUMNS}) "
        f"VALUES ({code}, NEW.platform_id, NEW.{column}, NEW.id);\n"
        "END IF;"
        for code, column in IDENTITY_PROVIDERS
    )


def _mysql_triggers() -> list[str]:
    unchanged = " AND ".join(f"NEW.{c} <=> OLD.{c}" for c in _TRACKED_COLUMNS)
    inserts = _mysql_inserts()
    return [
        f"CREATE TRIGGER {TABLE}_ai AFTER INSERT ON roms\n"
        f"FOR EACH ROW\nBEGIN\n{inserts}\nEND",
        f"CREATE TRIGGER {TABLE}_au AFTER UPDATE ON roms\n"  # nosec B608
        f"FOR EACH ROW\nBEGIN\n"
        f"IF NOT ({unchanged}) THEN\n"
        f"DELETE FROM {TABLE} WHERE rom_id = NEW.id;\n"
        f"{inserts}\n"
        f"END IF;\n"
        f"END",
    ]


def _postgres_trigger_function() -> str:
    unchanged = " AND ".join(
        f"NEW.{c} IS NOT DISTINCT FROM OLD.{c}" for c in _TRACKED_COLUMNS
    )
    inserts = "\n".join(
        f"    IF NEW.{column} IS NOT NULL THEN\n"  # nosec B608
        f"        INSERT INTO {TABLE} ({_COLUMNS})\n"
        f"        VALUES ({code}, NEW.platform_id, NEW.{column}, NEW.id)\n"
        f"        ON CONFLICT DO NOTHING;\n"
        f"    END IF;"
        for code, column in IDENTITY_PROVIDERS
    )
    return f"""
CREATE OR REPLACE FUNCTION romm_sync_rom_identity_keys() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF {unchanged} THEN
            RETURN NULL;
        END IF;
        DELETE FROM {TABLE} WHERE rom_id = NEW.id;
    END IF;

{inserts}

    RETURN NULL;
END $$
"""  # nosec B608


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

# Same column names as the definition this replaces, though a row now fills
# only its own provider's; nothing selects them, and a merged view skips them.
_PROVIDER_COLUMNS = ",\n    ".join(
    f"CASE WHEN k1.provider = {code} THEN k1.provider_id END AS {column}"
    for code, column in IDENTITY_PROVIDERS
)

_VIEW = f"""
CREATE VIEW sibling_roms AS
SELECT
    k1.rom_id AS rom_id,
    k2.rom_id AS sibling_rom_id,
    k1.platform_id AS platform_id,
    NOW() AS created_at,
    NOW() AS updated_at,
    {_PROVIDER_COLUMNS}
FROM {TABLE} k1
JOIN {TABLE} k2
    ON k1.provider = k2.provider
    AND k1.platform_id = k2.platform_id
    AND k1.provider_id = k2.provider_id
    AND k1.rom_id <> k2.rom_id
"""  # nosec B608


def upgrade() -> None:
    connection = op.get_bind()
    pg = is_postgresql(connection)

    # Every step is guarded so a re-run after a partial failure recovers
    # cleanly. MySQL/MariaDB auto-commit each DDL statement, so a crash
    # mid-migration leaves objects behind without advancing the alembic version.
    op.create_table(
        TABLE,
        sa.Column("provider", sa.SmallInteger(), nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.Integer(), nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("provider", "platform_id", "provider_id", "rom_id"),
        if_not_exists=True,
    )
    op.create_index(
        f"idx_{TABLE}_rom_id", TABLE, ["rom_id"], unique=False, if_not_exists=True
    )

    # Before the backfill: a rom written between the two steps would otherwise
    # never get its key rows, and nothing but a later edit of that rom would
    # notice. Both writes skip a row that is already there.
    if pg:
        op.execute(_postgres_trigger_function())
        op.execute(f"DROP TRIGGER IF EXISTS {TABLE}_aiu ON roms")
        op.execute(
            f"CREATE TRIGGER {TABLE}_aiu AFTER INSERT OR UPDATE ON roms\n"
            "FOR EACH ROW EXECUTE FUNCTION romm_sync_rom_identity_keys()"
        )
    else:
        op.execute(f"DROP TRIGGER IF EXISTS {TABLE}_ai")
        op.execute(f"DROP TRIGGER IF EXISTS {TABLE}_au")
        for trigger in _mysql_triggers():
            op.execute(trigger)

    for statement in _backfill(pg):
        op.execute(statement)

    # Without sampled statistics the optimizer estimates thousands of rows per
    # (provider, platform, provider id) and picks a worse join order for the
    # rest of the list query, leaving the gallery slower than before this ran.
    # A fresh install samples an empty table here, so a scan resamples after it
    # fills one (`db_rom_handler.refresh_identity_key_statistics`).
    op.execute(f"ANALYZE {'' if pg else 'TABLE '}{TABLE}")

    op.execute("DROP VIEW IF EXISTS sibling_roms")
    op.execute(_VIEW)


def downgrade() -> None:
    connection = op.get_bind()
    pg = is_postgresql(connection)

    op.execute("DROP VIEW IF EXISTS sibling_roms")
    op.execute(_legacy_view(pg))

    if pg:
        op.execute(f"DROP TRIGGER IF EXISTS {TABLE}_aiu ON roms")
        op.execute("DROP FUNCTION IF EXISTS romm_sync_rom_identity_keys()")
    else:
        op.execute(f"DROP TRIGGER IF EXISTS {TABLE}_ai")
        op.execute(f"DROP TRIGGER IF EXISTS {TABLE}_au")

    # The rom_id index backs the foreign key, so it goes with the table.
    op.drop_table(TABLE)


# ---------------------------------------------------------------------------
# Derive-on-read view definition (verbatim from 0073), used only by downgrade()
# ---------------------------------------------------------------------------


def _legacy_view(pg: bool) -> str:
    null_safe_equal_operator = "IS NOT DISTINCT FROM" if pg else "<=>"
    return f"""
CREATE VIEW sibling_roms AS
SELECT
    r1.id AS rom_id,
    r2.id AS sibling_rom_id,
    r1.platform_id AS platform_id,
    NOW() AS created_at,
    NOW() AS updated_at,
    CASE WHEN r1.igdb_id {null_safe_equal_operator} r2.igdb_id THEN r1.igdb_id END AS igdb_id,
    CASE WHEN r1.moby_id {null_safe_equal_operator} r2.moby_id THEN r1.moby_id END AS moby_id,
    CASE WHEN r1.ss_id {null_safe_equal_operator} r2.ss_id THEN r1.ss_id END AS ss_id,
    CASE WHEN r1.launchbox_id {null_safe_equal_operator} r2.launchbox_id THEN r1.launchbox_id END AS launchbox_id,
    CASE WHEN r1.ra_id {null_safe_equal_operator} r2.ra_id THEN r1.ra_id END AS ra_id,
    CASE WHEN r1.hasheous_id {null_safe_equal_operator} r2.hasheous_id THEN r1.hasheous_id END AS hasheous_id,
    CASE WHEN r1.tgdb_id {null_safe_equal_operator} r2.tgdb_id THEN r1.tgdb_id END AS tgdb_id
FROM
    roms r1
JOIN
    roms r2
ON
    r1.platform_id = r2.platform_id
    AND r1.id != r2.id
    AND (
        (r1.igdb_id = r2.igdb_id AND r1.igdb_id IS NOT NULL)
        OR
        (r1.moby_id = r2.moby_id AND r1.moby_id IS NOT NULL)
        OR
        (r1.ss_id = r2.ss_id AND r1.ss_id IS NOT NULL)
        OR
        (r1.launchbox_id = r2.launchbox_id AND r1.launchbox_id IS NOT NULL)
        OR
        (r1.ra_id = r2.ra_id AND r1.ra_id IS NOT NULL)
        OR
        (r1.hasheous_id = r2.hasheous_id AND r1.hasheous_id IS NOT NULL)
        OR
        (r1.tgdb_id = r2.tgdb_id AND r1.tgdb_id IS NOT NULL)
    )
"""  # nosec B608
