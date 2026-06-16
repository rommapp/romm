"""Add db-specific search indexes on roms.name and roms.fs_name

Revision ID: 0083_add_roms_search_indexes
Revises: 0082_save_origin_device
Create Date: 2026-06-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_mariadb, is_mysql, is_postgresql

# revision identifiers, used by Alembic.
revision = "0083_add_roms_search_indexes"
down_revision = "0082_save_origin_device"
branch_labels = None
depends_on = None

FULLTEXT_INDEX_NAME = "idx_roms_name_fs_name_fulltext"
PG_NAME_INDEX = "idx_roms_name_trgm"
PG_FS_NAME_INDEX = "idx_roms_fs_name_trgm"


def upgrade() -> None:
    bind = op.get_bind()

    if is_mysql(bind) or is_mariadb(bind):
        op.execute(
            sa.text(
                f"CREATE FULLTEXT INDEX {FULLTEXT_INDEX_NAME} "
                "ON roms (name, fs_name)"
            )
        )
    elif is_postgresql(bind):
        # pg_trgm is a trusted extension since PostgreSQL 13, so a non-superuser
        # with CREATE on the database can install it.
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        op.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS {PG_NAME_INDEX} "
                "ON roms USING gin (name gin_trgm_ops)"
            )
        )
        op.execute(
            sa.text(
                f"CREATE INDEX IF NOT EXISTS {PG_FS_NAME_INDEX} "
                "ON roms USING gin (fs_name gin_trgm_ops)"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()

    if is_mysql(bind) or is_mariadb(bind):
        op.execute(sa.text(f"DROP INDEX {FULLTEXT_INDEX_NAME} ON roms"))
    elif is_postgresql(bind):
        # Leave the pg_trgm extension in place; other objects may depend on it.
        op.execute(sa.text(f"DROP INDEX IF EXISTS {PG_FS_NAME_INDEX}"))
        op.execute(sa.text(f"DROP INDEX IF EXISTS {PG_NAME_INDEX}"))
