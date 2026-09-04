"""Store rom_files.last_modified with full precision

`last_modified` was created as a single-precision float, which on MariaDB and
MySQL rounds a current mtime to the nearest 128 seconds. Incremental file
scans compare it with the mtime on disk, so it needs the double precision the
rest of the stack already uses.

Revision ID: 0117_rom_files_mtime_double
Revises: 0116_sigil_title_ids
Create Date: 2026-08-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0117_rom_files_mtime_double"
down_revision = "0116_sigil_title_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.alter_column(
            "last_modified",
            existing_type=sa.Float(),
            type_=sa.Double(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.alter_column(
            "last_modified",
            existing_type=sa.Double(),
            type_=sa.Float(),
            existing_nullable=True,
        )
