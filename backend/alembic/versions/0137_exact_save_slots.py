"""Compare save slots exactly on MariaDB and MySQL, and index a slot's versions

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

SLOT_VERSIONS_INDEX = "ix_saves_rom_user_slot_updated"


def upgrade() -> None:
    op.create_index(
        SLOT_VERSIONS_INDEX,
        "saves",
        # Led by rom_id, which another index already serves as a foreign key:
        # a user_id lead would replace MariaDB's own index for that key.
        ["rom_id", "user_id", "slot", "updated_at"],
        if_not_exists=True,
    )
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
    # Some databases created this column with the table's folding collation.
    op.alter_column(
        "deleted_assets",
        "slot",
        existing_type=sa.String(length=255),
        type_=sa.String(length=255, collation=collation),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.drop_index(SLOT_VERSIONS_INDEX, table_name="saves", if_exists=True)
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
