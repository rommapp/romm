"""Add additional metadata IDs to sibling_roms view

Revision ID: 0048_sibling_roms_more_ids
Revises: 0047_smart_collections
Create Date: 2025-01-27 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import is_postgresql

# revision identifiers, used by Alembic.
revision = "0048_sibling_roms_more_ids"
down_revision = "0047_smart_collections"
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
                CASE WHEN r1.ss_id {null_safe_equal_operator} r2.ss_id THEN r1.ss_id END AS ss_id,
                CASE WHEN r1.launchbox_id {null_safe_equal_operator} r2.launchbox_id THEN r1.launchbox_id END AS launchbox_id,
                CASE WHEN r1.ra_id {null_safe_equal_operator} r2.ra_id THEN r1.ra_id END AS ra_id,
                CASE WHEN r1.hasheous_id {null_safe_equal_operator} r2.hasheous_id THEN r1.hasheous_id END AS hasheous_id,
                CASE WHEN r1.tgdb_id {null_safe_equal_operator} r2.tgdb_id THEN r1.tgdb_id END AS tgdb_id
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
                    OR
                    (r1.launchbox_id = r2.launchbox_id AND r1.launchbox_id IS NOT NULL)
                    OR
                    (r1.ra_id = r2.ra_id AND r1.ra_id IS NOT NULL)
                    OR
                    (r1.hasheous_id = r2.hasheous_id AND r1.hasheous_id IS NOT NULL)
                    OR
                    (r1.tgdb_id = r2.tgdb_id AND r1.tgdb_id IS NOT NULL)
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
