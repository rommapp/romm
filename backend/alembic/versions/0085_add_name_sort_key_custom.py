"""Add name_sort_key_custom column to roms

Tracks whether `roms.name_sort_key` is a user/metadata-supplied override (so it
is preserved across renames and rescans) or derived from `name` on write. New
rows default to derived (false), and existing rows are backfilled the same way.

Revision ID: 0085_add_name_sort_key_custom
Revises: 0084_add_roms_search_index
Create Date: 2026-05-31 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "0085_add_name_sort_key_custom"
down_revision = "0084_add_roms_search_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "name_sort_key_custom",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            ),
            if_not_exists=True,
        )
        # Drop the server-side default; the model supplies the Python default.
        batch_op.alter_column("name_sort_key_custom", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("name_sort_key_custom", if_exists=True)
