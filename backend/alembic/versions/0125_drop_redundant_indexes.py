"""Drop the indexes that duplicate a wider one

Each of these is the leftmost prefix of another index on the same table, so it
serves no query of its own and only costs writes:

- ``idx_rom_files_rom_id`` of ``idx_rom_files_rom_id_category``.
- ``idx_rom_notes_rom_user`` of ``unique_rom_user_note_title``.
- ``ix_devices_user_id`` of ``ix_devices_user_client_identifier``.
- ``ix_memory_card_versions_card`` of ``ix_memory_card_versions_card_hash``.

Every column here still leads a qualifying index, so MariaDB re-points its
foreign key rather than refusing the drop.

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
    ("devices", "ix_devices_user_id", ["user_id"]),
    ("memory_card_versions", "ix_memory_card_versions_card", ["memory_card_id"]),
)


def upgrade() -> None:
    for table, name, _columns in REDUNDANT_INDEXES:
        op.drop_index(name, table_name=table, if_exists=True)


def downgrade() -> None:
    for table, name, columns in REDUNDANT_INDEXES:
        op.create_index(name, table, columns, unique=False, if_not_exists=True)
