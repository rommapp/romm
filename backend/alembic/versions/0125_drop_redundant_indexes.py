"""Drop two indexes that duplicate a wider one

Each of these is fully served by another index on the same table, so it only
costs writes:

- ``idx_rom_files_rom_id`` (from 0079) is the leftmost prefix of
  ``idx_rom_files_rom_id_category`` (from 0109).
- ``idx_rom_notes_rom_user`` is the leftmost prefix of the
  ``unique_rom_user_note_title`` constraint on ``(rom_id, user_id, title)``.

MariaDB re-points a foreign key at another qualifying index when the one it was
using is dropped, and both columns here keep such an index, so the constraints
stay enforced.

Revision ID: 0125_drop_redundant_indexes
Revises: 0124_gallery_and_fk_indexes
Create Date: 2026-09-07 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0125_drop_redundant_indexes"
down_revision = "0124_gallery_and_fk_indexes"
branch_labels = None
depends_on = None

REDUNDANT_INDEXES = (
    ("rom_files", "idx_rom_files_rom_id", ["rom_id"]),
    ("rom_notes", "idx_rom_notes_rom_user", ["rom_id", "user_id"]),
)


def upgrade() -> None:
    for table, name, _columns in REDUNDANT_INDEXES:
        op.drop_index(name, table_name=table, if_exists=True)


def downgrade() -> None:
    for table, name, columns in REDUNDANT_INDEXES:
        op.create_index(name, table, columns, unique=False, if_not_exists=True)
