"""Add deleted_saves table

Revision ID: 0136_deleted_saves
Revises: 0135_drop_play_session_sync_link
Create Date: 2026-09-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0136_deleted_saves"
down_revision = "0135_drop_play_session_sync_link"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_deleted_saves_user_rom_slot"
ROM_INDEX_NAME = "ix_deleted_saves_rom_id"


def upgrade() -> None:
    op.create_table(
        "deleted_saves",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.String(length=255), nullable=False),
        sa.Column("content_hashes", sa.JSON(), nullable=False),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        INDEX_NAME,
        "deleted_saves",
        ["user_id", "rom_id", "slot"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        ROM_INDEX_NAME, "deleted_saves", ["rom_id"], unique=False, if_not_exists=True
    )


def downgrade() -> None:
    op.drop_table("deleted_saves", if_exists=True)
