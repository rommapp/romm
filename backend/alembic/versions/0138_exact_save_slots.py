"""Compare save slots exactly, index a slot's versions, and time their removal

Revision ID: 0138_exact_save_slots
Revises: 0137_rename_system_groups
Create Date: 2026-09-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from models.assets import SAVE_SLOT_MAX_LENGTH, SAVE_SLOT_VERSIONS_INDEX
from utils.database import CustomJSON, exact_collation

# revision identifiers, used by Alembic.
revision = "0138_exact_save_slots"
down_revision = "0137_rename_system_groups"
branch_labels = None
depends_on = None

# Each slot column and its nullability. deleted_assets is included for
# databases that ran 0136 before it created the column exact.
SLOT_COLUMNS = (("saves", True), ("deleted_assets", False))


def upgrade() -> None:
    op.add_column(
        "deleted_assets",
        sa.Column("removed_at", CustomJSON(), nullable=True),
        if_not_exists=True,
    )
    collation = exact_collation(op.get_bind())
    if collation is not None:
        for table, nullable in SLOT_COLUMNS:
            # Skipped once done, so a run that died partway resumes without a rebuild.
            if _slot_collation(table) != collation:
                op.alter_column(
                    table,
                    "slot",
                    existing_type=sa.String(length=SAVE_SLOT_MAX_LENGTH),
                    type_=sa.String(length=SAVE_SLOT_MAX_LENGTH, collation=collation),
                    existing_nullable=nullable,
                )
    # After the collation change, which would otherwise rebuild it.
    op.create_index(
        SAVE_SLOT_VERSIONS_INDEX,
        "saves",
        # Led by rom_id, which another index already serves as a foreign key:
        # a user_id lead would replace MariaDB's own index for that key.
        ["rom_id", "user_id", "slot", "updated_at"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column("deleted_assets", "removed_at", if_exists=True)
    op.drop_index(SAVE_SLOT_VERSIONS_INDEX, table_name="saves", if_exists=True)
    collation = exact_collation(op.get_bind())
    # 0136 creates deleted_assets.slot exact, so only saves.slot reverts.
    if collation is None or _slot_collation("saves") != collation:
        return
    # Without a collation the column takes the table's default back.
    op.alter_column(
        "saves",
        "slot",
        existing_type=sa.String(length=SAVE_SLOT_MAX_LENGTH),
        type_=sa.String(length=SAVE_SLOT_MAX_LENGTH),
        existing_nullable=True,
    )


def _slot_collation(table: str) -> str | None:
    [column] = [
        column
        for column in sa.inspect(op.get_bind()).get_columns(table)
        if column["name"] == "slot"
    ]
    return column["type"].collation
