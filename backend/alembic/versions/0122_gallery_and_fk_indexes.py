"""Add the gallery sort/scope indexes and the PostgreSQL foreign-key indexes

Two groups of indexes, both filling gaps left by earlier index passes.

Portable, on every backend:

- ``screenshots (rom_id, user_id)``. ``Save.screenshot`` / ``State.screenshot``
  resolve a thumbnail per row, so this lookup runs once per card on the
  continue-playing rail. ``0093_states_rom_user_index`` added the equivalent to
  ``states`` and noted ``saves`` already had it; ``screenshots`` was missed.
- ``rom_user (user_id, rom_id)`` and ``rom_user (user_id, last_played)``.
  ``unique_rom_user_props`` leads with ``rom_id``, which covers the gallery's
  outer join but not the reverse direction, where sorting or scoping by a
  per-user column starts from this table.
- ``roms (platform_id, name_sort_key)``. The gallery is browsed one platform at
  a time and ordered by name, and no index carried both columns, so every page
  filesorted the whole platform.

PostgreSQL only:

MariaDB and MySQL create an index for every foreign key whose column is not
already some index's leftmost prefix; PostgreSQL does not. The columns below
are queried directly or walked by ``ON DELETE`` and were relying on that
implicit index, so on PostgreSQL alone they need a real one. Creating them
everywhere would leave MariaDB with two identical indexes per column, so they
are dialect-gated here and excluded from autogenerate in ``alembic/env.py``,
the same treatment the dialect-specific search indexes get.

Revision ID: 0122_gallery_and_fk_indexes
Revises: 0121_state_disc_file
Create Date: 2026-09-07 00:00:00.000000

"""

from alembic import op

from utils.database import POSTGRESQL_FK_INDEXES, is_postgresql

# revision identifiers, used by Alembic.
revision = "0122_gallery_and_fk_indexes"
down_revision = "0121_state_disc_file"
branch_labels = None
depends_on = None

# (table, index name, columns)
PORTABLE_INDEXES = (
    ("screenshots", "ix_screenshots_rom_user", ["rom_id", "user_id"]),
    ("rom_user", "ix_rom_user_user_rom", ["user_id", "rom_id"]),
    ("rom_user", "ix_rom_user_user_last_played", ["user_id", "last_played"]),
    ("roms", "idx_roms_platform_name_sort_key", ["platform_id", "name_sort_key"]),
)


def upgrade() -> None:
    for table, name, columns in PORTABLE_INDEXES:
        op.create_index(name, table, columns, unique=False, if_not_exists=True)

    if is_postgresql(op.get_bind()):
        for table, name, columns in POSTGRESQL_FK_INDEXES:
            op.create_index(name, table, columns, unique=False, if_not_exists=True)


def downgrade() -> None:
    if is_postgresql(op.get_bind()):
        for table, name, _columns in reversed(POSTGRESQL_FK_INDEXES):
            op.drop_index(name, table_name=table, if_exists=True)

    for table, name, _columns in reversed(PORTABLE_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
