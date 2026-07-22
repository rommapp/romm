"""Mirror the ROM filter values into a narrow, trigger-maintained table

Building the filter dropdowns aggregated the facet columns straight off
``roms``. Those columns are cheap to compute since 0098, but they live inline
with the raw provider-metadata blobs, so the aggregation still had to read
every row of a multi-gigabyte table: on a ~90k-game library that is seconds of
pure disk reading on any database whose buffer pool is smaller than the table
(the stock 128-256 MB defaults always are).

``roms_facets`` holds only the filter values (a few MB for the same library) and
is kept in sync by AFTER INSERT/UPDATE triggers on ``roms``, so every write path
(ORM, bulk update, scan) stays consistent without an application hook. Deletes
ride the ``ON DELETE CASCADE`` foreign key.

Revision ID: 0100_roms_facets_table
Revises: 0099_platform_description
Create Date: 2026-07-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

from utils.database import CustomJSON, is_postgresql

# revision identifiers, used by Alembic.
revision = "0100_roms_facets_table"
down_revision = "0099_platform_description"
branch_labels = None
depends_on = None


# (roms_facets column, roms source column)
_MIRRORED_COLUMNS = [
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

_TARGET_COLUMNS = ", ".join(target for target, _ in _MIRRORED_COLUMNS)
_SOURCE_COLUMNS = ", ".join(source for _, source in _MIRRORED_COLUMNS)

# Backfilled into the empty table before the triggers exist, so no row can
# conflict and no upsert guard is needed.
_BACKFILL_SQL = (
    f"INSERT INTO roms_facets (rom_id, {_TARGET_COLUMNS})\n"  # nosec B608
    f"SELECT id, {_SOURCE_COLUMNS} FROM roms"
)

_MYSQL_UPSERT_BODY = (
    f"INSERT INTO roms_facets (rom_id, {_TARGET_COLUMNS})\n"  # nosec B608
    + "VALUES (NEW.id, "
    + ", ".join(f"NEW.{source}" for _, source in _MIRRORED_COLUMNS)
    + ")\nON DUPLICATE KEY UPDATE\n"
    + ",\n".join(f"{target} = VALUES({target})" for target, _ in _MIRRORED_COLUMNS)
    + ",\nupdated_at = CURRENT_TIMESTAMP"
)

_MYSQL_TRIGGERS = {
    "roms_facets_after_insert": "AFTER INSERT",
    "roms_facets_after_update": "AFTER UPDATE",
}

_POSTGRES_SYNC_FN = f"""
CREATE OR REPLACE FUNCTION romm_sync_rom_facets() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO roms_facets (rom_id, {_TARGET_COLUMNS})
    VALUES (NEW.id, {", ".join(f"NEW.{source}" for _, source in _MIRRORED_COLUMNS)})
    ON CONFLICT (rom_id) DO UPDATE SET
        {", ".join(f"{target} = EXCLUDED.{target}" for target, _ in _MIRRORED_COLUMNS)},
        updated_at = NOW();
    RETURN NULL;
END $$
"""  # nosec B608

_POSTGRES_TRIGGER = """
CREATE TRIGGER roms_facets_sync AFTER INSERT OR UPDATE ON roms
    FOR EACH ROW EXECUTE FUNCTION romm_sync_rom_facets()
"""


def upgrade() -> None:
    op.create_table(
        "roms_facets",
        sa.Column(
            "rom_id",
            sa.Integer(),
            sa.ForeignKey("roms.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("genres", CustomJSON(), nullable=True),
        sa.Column("franchises", CustomJSON(), nullable=True),
        sa.Column("collections", CustomJSON(), nullable=True),
        sa.Column("companies", CustomJSON(), nullable=True),
        sa.Column("game_modes", CustomJSON(), nullable=True),
        sa.Column("age_ratings", CustomJSON(), nullable=True),
        sa.Column("player_count", sa.String(length=100), nullable=True),
        sa.Column("regions", CustomJSON(), nullable=True),
        sa.Column("languages", CustomJSON(), nullable=True),
        sa.Column("tags", CustomJSON(), nullable=True),
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
    )
    op.create_index("idx_roms_facets_platform_id", "roms_facets", ["platform_id"])

    op.execute(_BACKFILL_SQL)

    if is_postgresql(op.get_bind()):
        op.execute(_POSTGRES_SYNC_FN)
        op.execute(_POSTGRES_TRIGGER)
    else:
        for name, timing in _MYSQL_TRIGGERS.items():
            op.execute(
                f"CREATE TRIGGER {name} {timing} ON roms\n"
                f"FOR EACH ROW\n{_MYSQL_UPSERT_BODY}"
            )


def downgrade() -> None:
    if is_postgresql(op.get_bind()):
        op.execute("DROP TRIGGER IF EXISTS roms_facets_sync ON roms")
        op.execute("DROP FUNCTION IF EXISTS romm_sync_rom_facets()")
    else:
        for name in _MYSQL_TRIGGERS:
            op.execute(f"DROP TRIGGER IF EXISTS {name}")

    op.drop_index("idx_roms_facets_platform_id", table_name="roms_facets")
    op.drop_table("roms_facets")
