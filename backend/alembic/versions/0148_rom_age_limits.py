"""Age limits: each ROM's minimum age, and per-group/per-user limits on it

`roms.min_age` holds the strictest age any of a ROM's ratings sets, mirrored
into `roms_facets` so the stats queries can apply a limit without a join.
Groups and users gain an age limit and a "hide unrated" switch, and
`age_rating_exemptions` lets a ROM through a limit for one user or group.

Revision ID: 0148_rom_age_limits
Revises: 0147_rom_file_title_ids
Create Date: 2026-10-03 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.age_ratings import compute_min_age
from utils.database import MIN_AGE_COLUMN, CustomJSON, column_names, is_postgresql
from utils.roms_columns import TAG_COLUMNS, ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0148_rom_age_limits"
down_revision = "0147_rom_file_title_ids"
branch_labels = None
depends_on = None

BATCH_SIZE = 1000
EXEMPTIONS = "age_rating_exemptions"

# (column, key) of each source `compute_min_age` reads, a frozen snapshot of
# `MIN_AGE_SOURCE_COLUMNS` so a later source can't change this revision.
AGE_SOURCES = (
    ("manual_metadata", "age_ratings"),
    ("igdb_metadata", "age_ratings"),
    ("ss_metadata", "age_ratings"),
    ("launchbox_metadata", "esrb"),
    ("steam_metadata", "required_age"),
)

ROMS = sa.table(
    "roms",
    sa.column("id", sa.Integer()),
    sa.column(MIN_AGE_COLUMN, sa.Integer()),
    *(sa.column(column, CustomJSON()) for column, _ in AGE_SOURCES),
)

# Mirrored into roms_facets by the triggers: 0123's list, in its order.
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


def _suspend_facets_sync(pg: bool) -> None:
    """Stop the roms_facets triggers so the backfill skips a per-row upsert."""
    if pg:
        op.execute("ALTER TABLE roms DISABLE TRIGGER roms_facets_sync")
        return
    for name in _MYSQL_TRIGGERS:
        op.execute(f"DROP TRIGGER IF EXISTS {name}")


def _mirror_min_age(pg: bool) -> None:
    """Copy the backfilled ages into roms_facets in one statement."""
    if pg:
        op.execute(
            "UPDATE roms_facets SET min_age = roms.min_age FROM roms "
            "WHERE roms.id = roms_facets.rom_id AND roms.min_age IS NOT NULL"
        )
        return
    op.execute(
        "UPDATE roms_facets JOIN roms ON roms.id = roms_facets.rom_id "
        "SET roms_facets.min_age = roms.min_age WHERE roms.min_age IS NOT NULL"
    )


def _fill_min_age(conn: sa.Connection) -> None:
    """Rate every ROM, in keyset batches."""
    # JSON paths keep the large metadata blobs out of the read.
    ratings = [ROMS.c[column][key] for column, key in AGE_SOURCES]
    last_id = 0
    while rows := conn.execute(
        sa.select(ROMS.c.id, *ratings)
        .where(ROMS.c.id > last_id)
        .order_by(ROMS.c.id)
        .limit(BATCH_SIZE)
    ).all():
        ages = {
            rom_id: compute_min_age(
                {
                    column: {key: value}
                    for (column, key), value in zip(AGE_SOURCES, values, strict=True)
                }
            )
            for rom_id, *values in rows
        }
        rated = {rom_id: age for rom_id, age in ages.items() if age is not None}
        # One statement per batch, since a round trip per row dominates.
        if rated:
            conn.execute(
                sa.update(ROMS)
                .where(ROMS.c.id.in_(rated))
                .values({MIN_AGE_COLUMN: sa.case(rated, value=ROMS.c.id)})
            )
        last_id = rows[-1][0]


def upgrade() -> None:
    conn = op.get_bind()
    pg = is_postgresql(conn)

    ensure_roms_columns(conn)
    op.add_column(
        "roms_facets",
        sa.Column(MIN_AGE_COLUMN, sa.Integer(), nullable=True),
        if_not_exists=True,
    )
    _suspend_facets_sync(pg)
    _fill_min_age(conn)
    _rebuild_triggers(pg, _BASE_MIRRORED_COLUMNS + [(MIN_AGE_COLUMN, MIN_AGE_COLUMN)])
    if pg:
        op.execute("ALTER TABLE roms ENABLE TRIGGER roms_facets_sync")
    _mirror_min_age(pg)

    with op.batch_alter_table("permission_groups") as batch_op:
        batch_op.add_column(
            sa.Column("age_limit", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column(
                "hide_unrated_roms",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            if_not_exists=True,
        )
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("age_limit", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("hide_unrated_roms", sa.Boolean(), nullable=True),
            if_not_exists=True,
        )

    op.create_table(
        EXEMPTIONS,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["group_id"], ["permission_groups.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rom_id", "user_id", "group_id", name="uq_age_exemption"),
        sa.CheckConstraint(
            "(user_id IS NULL) <> (group_id IS NULL)",
            name="ck_age_exemption_one_principal",
        ),
        if_not_exists=True,
    )
    with op.batch_alter_table(EXEMPTIONS) as batch_op:
        for column in ("rom_id", "user_id", "group_id"):
            batch_op.create_index(
                f"ix_{EXEMPTIONS}_{column}", [column], if_not_exists=True
            )


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_table(EXEMPTIONS, if_exists=True)
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("hide_unrated_roms", if_exists=True)
        batch_op.drop_column("age_limit", if_exists=True)
    with op.batch_alter_table("permission_groups") as batch_op:
        batch_op.drop_column("hide_unrated_roms", if_exists=True)
        batch_op.drop_column("age_limit", if_exists=True)

    _rebuild_triggers(is_postgresql(conn), _BASE_MIRRORED_COLUMNS)
    # MySQL has no DROP COLUMN IF EXISTS.
    for table in ("roms_facets", "roms"):
        if MIN_AGE_COLUMN in column_names(conn, table):
            op.drop_column(table, MIN_AGE_COLUMN)
