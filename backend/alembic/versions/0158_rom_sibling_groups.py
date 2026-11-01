"""Group sibling ROMs by connected component and key `sibling_roms` on it

`sibling_roms` paired ROMs sharing any one identity key, while the gallery's
`group_by_meta_id` window partitioned on the first non-null id in a fixed
provider order. A ROM matched by IGDB and ScreenScraper and its sibling matched
by ScreenScraper alone were siblings on the game page but two gallery cards.
Both now read `rom_sibling_groups`, the transitive closure of the keys.

Revision ID: 0158_rom_sibling_groups
Revises: 0157_rom_custom_sort_key_flag
Create Date: 2026-10-31 00:00:00.000000

"""

from itertools import batched

import sqlalchemy as sa
from alembic import op

from utils.sibling_groups import sibling_groups

# revision identifiers, used by Alembic.
revision = "0158_rom_sibling_groups"
down_revision = "0157_rom_custom_sort_key_flag"
branch_labels = None
depends_on = None

TABLE = "rom_sibling_groups"
INDEX = "idx_rom_sibling_groups_group_id"
_BATCH_SIZE = 1000

_VIEW = f"""
CREATE VIEW sibling_roms AS
SELECT
    g1.rom_id AS rom_id,
    g2.rom_id AS sibling_rom_id,
    NOW() AS created_at,
    NOW() AS updated_at
FROM {TABLE} g1
JOIN {TABLE} g2
    ON g1.group_id = g2.group_id
    AND g1.rom_id <> g2.rom_id
"""  # nosec B608


def _backfill() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT rom_id, provider, platform_id, provider_id FROM rom_identity_keys"
        )
    ).all()
    groups = sibling_groups(
        (rom_id, (provider, platform_id, provider_id))
        for rom_id, provider, platform_id, provider_id in rows
    )

    # A re-run after a partial failure starts the fill over.
    op.execute(f"DELETE FROM {TABLE}")  # nosec B608
    insert = sa.text(
        f"INSERT INTO {TABLE} (rom_id, group_id) VALUES (:rom_id, :group_id)"  # nosec B608
    )
    for chunk in batched(groups.items(), _BATCH_SIZE, strict=False):
        connection.execute(
            insert,
            [{"rom_id": rom_id, "group_id": group_id} for rom_id, group_id in chunk],
        )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("rom_id"),
        if_not_exists=True,
    )
    op.create_index(INDEX, TABLE, ["group_id", "rom_id"], if_not_exists=True)

    _backfill()

    op.execute("DROP VIEW IF EXISTS sibling_roms")
    op.execute(_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS sibling_roms")
    op.execute(_IDENTITY_KEYS_VIEW)
    op.drop_table(TABLE, if_exists=True)


# ---------------------------------------------------------------------------
# The view as 0127 left it, used only by downgrade()
# ---------------------------------------------------------------------------

_IDENTITY_PROVIDERS = (
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

_PROVIDER_COLUMNS = ",\n    ".join(
    f"CASE WHEN k1.provider = {code} THEN k1.provider_id END AS {column}"
    for code, column in _IDENTITY_PROVIDERS
)

_IDENTITY_KEYS_VIEW = f"""
CREATE VIEW sibling_roms AS
SELECT
    k1.rom_id AS rom_id,
    k2.rom_id AS sibling_rom_id,
    k1.platform_id AS platform_id,
    NOW() AS created_at,
    NOW() AS updated_at,
    {_PROVIDER_COLUMNS}
FROM rom_identity_keys k1
JOIN rom_identity_keys k2
    ON k1.provider = k2.provider
    AND k1.platform_id = k2.platform_id
    AND k1.provider_id = k2.provider_id
    AND k1.rom_id <> k2.rom_id
"""  # nosec B608
