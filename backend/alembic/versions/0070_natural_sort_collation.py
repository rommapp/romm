"""Add natural sort collation for PostgreSQL

Revision ID: 0070_natural_sort_collation
Revises: 0069_sibling_roms_fs_name
Create Date: 2026-02-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0070_natural_sort_collation"
down_revision = "0069_sibling_roms_fs_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if is_postgresql(connection):
        connection.execute(
            sa.text(
                "CREATE COLLATION IF NOT EXISTS natural_sort (provider = icu, locale = 'en-u-kn-true')"
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    if is_postgresql(connection):
        connection.execute(sa.text("DROP COLLATION IF EXISTS natural_sort"))
