"""Add ScreenScraper data

Revision ID: 0035_screenscraper
Revises: 0034_virtual_collections_db_view
Create Date: 2025-01-02 18:58:55.557123

"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0035_screenscraper"
down_revision = "0034_virtual_collections_db_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ss_id", sa.Integer(), nullable=True), if_not_exists=True
        )

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ss_id", sa.Integer(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("ss_metadata", CustomJSON(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("url_manual", sa.Text(), nullable=True), if_not_exists=True
        )
        batch_op.add_column(
            sa.Column("path_manual", sa.Text(), nullable=True), if_not_exists=True
        )
        batch_op.create_index(
            "idx_roms_ss_id", ["ss_id"], unique=False, if_not_exists=True
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_ss_id", if_exists=True)
        batch_op.drop_column("ss_id", if_exists=True)
        batch_op.drop_column("ss_metadata", if_exists=True)
        batch_op.drop_column("url_manual", if_exists=True)
        batch_op.drop_column("path_manual", if_exists=True)

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("ss_id", if_exists=True)
