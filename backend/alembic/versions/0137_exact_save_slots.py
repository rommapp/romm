"""Compare save slots exactly on MariaDB and MySQL

Revision ID: 0137_exact_save_slots
Revises: 0136_deleted_assets
Create Date: 2026-09-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import exact_collation

# revision identifiers, used by Alembic.
revision = "0137_exact_save_slots"
down_revision = "0136_deleted_assets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    collation = exact_collation(op.get_bind())
    if collation is None:
        return
    op.alter_column(
        "saves",
        "slot",
        existing_type=sa.String(length=255),
        type_=sa.String(length=255, collation=collation),
        existing_nullable=True,
    )


def downgrade() -> None:
    if exact_collation(op.get_bind()) is None:
        return
    # Without a collation the column takes the table's default back.
    op.alter_column(
        "saves",
        "slot",
        existing_type=sa.String(length=255),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
