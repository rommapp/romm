"""empty message

Revision ID: 0024_sibling_roms_db_view
Revises: 0023_make_columns_non_nullable
Create Date: 2024-08-08 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0024_sibling_roms_db_view"
down_revision = "0023_make_columns_non_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            CREATE VIEW sibling_roms AS
            SELECT
                r1.id AS rom_id,
                GROUP_CONCAT(r2.id) AS sibling_rom_ids
            FROM
                roms r1
            LEFT JOIN 
                roms r2 
            ON 
                r1.platform_id = r2.platform_id
                AND r1.id != r2.id
                AND (
                    (r1.igdb_id = r2.igdb_id AND r1.igdb_id IS NOT NULL AND r1.igdb_id != '')
                    OR
                    (r1.moby_id = r2.moby_id AND r1.moby_id IS NOT NULL AND r1.moby_id != '')
                )
            GROUP BY
                r1.id;
            """
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            DROP VIEW sibling_roms;
            """
        ),
    )
