"""Add the gallery sort/scope indexes and the PostgreSQL foreign-key indexes

Four composites the gallery needs and no index carried: ``screenshots (rom_id,
user_id)`` for the thumbnail of every save/state card, the equivalent of what
0093 added to ``states``; ``rom_user (user_id, rom_id)`` and ``rom_user
(user_id, last_played)`` for scoping or sorting from that table rather than
from ``roms``; and ``roms (platform_id, name_sort_key)`` so a per-platform page
no longer filesorts. ``POSTGRESQL_FK_INDEXES`` then covers the foreign keys
MariaDB and MySQL index implicitly and PostgreSQL does not.

Revision ID: 0124_gallery_and_fk_indexes
Revises: 0123_recommendation_metadata
Create Date: 2026-09-07 00:00:00.000000

"""

from alembic import op

from utils.database import POSTGRESQL_FK_INDEXES, is_postgresql

# revision identifiers, used by Alembic.
revision = "0124_gallery_and_fk_indexes"
down_revision = "0123_recommendation_metadata"
branch_labels = None
depends_on = None

# (table, index name, columns)
PORTABLE_INDEXES = (
    ("screenshots", "ix_screenshots_rom_user", ["rom_id", "user_id"]),
    ("rom_user", "ix_rom_user_user_rom", ["user_id", "rom_id"]),
    ("rom_user", "ix_rom_user_user_last_played", ["user_id", "last_played"]),
    ("roms", "idx_roms_platform_name_sort_key", ["platform_id", "name_sort_key"]),
)

# Implicit MariaDB/MySQL foreign-key indexes the composites above absorb, named
# as InnoDB names them. Only needed to reverse this migration.
DISPLACED_FK_INDEXES = (
    ("screenshots", "rom_id", ["rom_id"]),
    ("rom_user", "user_id", ["user_id"]),
)


def upgrade() -> None:
    for table, name, columns in PORTABLE_INDEXES:
        op.create_index(name, table, columns, unique=False, if_not_exists=True)

    if is_postgresql(op.get_bind()):
        for table, name, column in POSTGRESQL_FK_INDEXES:
            op.create_index(name, table, [column], unique=False, if_not_exists=True)


def downgrade() -> None:
    bind = op.get_bind()

    if is_postgresql(bind):
        for table, name, _column in reversed(POSTGRESQL_FK_INDEXES):
            op.drop_index(name, table_name=table, if_exists=True)
    else:
        # InnoDB discarded the implicit index when it re-pointed the constraint
        # at the composite, and the drop below fails without one.
        for table, name, columns in DISPLACED_FK_INDEXES:
            op.create_index(name, table, columns, unique=False, if_not_exists=True)

    for table, name, _columns in reversed(PORTABLE_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
