"""Index the remaining gallery sort columns

Nothing matched the `ORDER BY <column>, id` the gallery emits: `created_at`
had no index at all, and the composites leading with `platform_id` carry
another column before `id`. All three are NOT NULL, so pairing each key with
the `id` tiebreak is enough.

Revision ID: 0130_gallery_sort_indexes
Revises: 0129_indexed_gallery_sorts
Create Date: 2026-09-19 00:00:00.000000

"""

from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision = "0130_gallery_sort_indexes"
down_revision = "0129_indexed_gallery_sorts"
branch_labels = None
depends_on = None

INDEXES = (
    ("idx_roms_platform_id_sorted", ["platform_id", "id"]),
    ("idx_roms_fs_size_bytes_sorted", ["fs_size_bytes", "id"]),
    ("idx_roms_created_at_sorted", ["created_at", "id"]),
)


def upgrade() -> None:
    for name, columns in INDEXES:
        op.create_index(name, "roms", columns, if_not_exists=True)


def downgrade() -> None:
    for name, _ in INDEXES:
        op.drop_index(name, table_name="roms", if_exists=True)
