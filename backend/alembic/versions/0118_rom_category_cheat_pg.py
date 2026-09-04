"""Add the CHEAT rom_files category to the PostgreSQL enum

Migration 0067 created the value with `ENUM.create(checkfirst=True)`, which
is a no-op once the type exists, so PostgreSQL databases never received it
and every cheat file failed to insert during scans. MariaDB and MySQL got it
through the column rewrite and need nothing here.

Revision ID: 0118_rom_category_cheat_pg
Revises: 0117_rom_files_mtime_double
Create Date: 2026-08-24 00:00:00.000000

"""

from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0118_rom_category_cheat_pg"
down_revision = "0117_rom_files_mtime_double"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not is_postgresql(op.get_bind()):
        return

    # `ALTER TYPE ... ADD VALUE` must run outside a transaction in PostgreSQL.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE romfilecategory ADD VALUE IF NOT EXISTS 'CHEAT'")


def downgrade() -> None:
    # PostgreSQL cannot remove enum values, and the other backends are
    # untouched by the upgrade.
    pass
