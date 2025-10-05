"""empty message

Revision ID: 0038_add_ssid_to_sibling_roms
Revises: 0037_virtual_rom_columns
Create Date: 2025-04-23 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0038_add_ssid_to_sibling_roms"
down_revision = "0037_virtual_rom_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    null_safe_equal_operator = (
        "IS NOT DISTINCT FROM" if is_postgresql(connection) else "<=>"
    )

    connection.execute(
        sa.text(
            f"""
            CREATE OR REPLACE VIEW sibling_roms AS
            SELECT
                r1.id AS rom_id,
                r2.id AS sibling_rom_id,
                r1.platform_id AS platform_id,
                NOW() AS created_at,
                NOW() AS updated_at,
                CASE WHEN r1.igdb_id {null_safe_equal_operator} r2.igdb_id THEN r1.igdb_id END AS igdb_id,
                CASE WHEN r1.moby_id {null_safe_equal_operator} r2.moby_id THEN r1.moby_id END AS moby_id,
                CASE WHEN r1.ss_id {null_safe_equal_operator} r2.ss_id THEN r1.ss_id END AS ss_id
            FROM
                roms r1
            JOIN
                roms r2
            ON
                r1.platform_id = r2.platform_id
                AND r1.id != r2.id
                AND (
                    (r1.igdb_id = r2.igdb_id AND r1.igdb_id IS NOT NULL)
                    OR
                    (r1.moby_id = r2.moby_id AND r1.moby_id IS NOT NULL)
                    OR
                    (r1.ss_id = r2.ss_id AND r1.ss_id IS NOT NULL)
                );
            """  # nosec B608
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    null_safe_equal_operator = (
        "IS NOT DISTINCT FROM" if is_postgresql(connection) else "<=>"
    )

    connection.execute(sa.text("DROP VIEW IF EXISTS sibling_roms;"))

    connection.execute(
        sa.text(
            f"""
            CREATE VIEW sibling_roms AS
            SELECT
                r1.id AS rom_id,
                r2.id AS sibling_rom_id,
                r1.platform_id AS platform_id,
                NOW() AS created_at,
                NOW() AS updated_at,
                CASE WHEN r1.igdb_id {null_safe_equal_operator} r2.igdb_id THEN r1.igdb_id END AS igdb_id,
                CASE WHEN r1.moby_id {null_safe_equal_operator} r2.moby_id THEN r1.moby_id END AS moby_id
            FROM
                roms r1
            JOIN
                roms r2
            ON
                r1.platform_id = r2.platform_id
                AND r1.id != r2.id
                AND (
                    (r1.igdb_id = r2.igdb_id AND r1.igdb_id IS NOT NULL)
                    OR
                    (r1.moby_id = r2.moby_id AND r1.moby_id IS NOT NULL)
                );
            """  # nosec B608
        ),
    )
