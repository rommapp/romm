"""Add Steam library import: linked accounts, store-only roms, owned games

Revision ID: 0159_steam_library
Revises: 0158_platform_first_release_year
Create Date: 2026-10-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import column_names
from utils.roms_columns import ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0159_steam_library"
down_revision = "0158_platform_first_release_year"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    ensure_roms_columns(connection)

    user_columns = column_names(connection, "users")
    with op.batch_alter_table("users", schema=None) as batch_op:
        if "steam_id" not in user_columns:
            batch_op.add_column(sa.Column("steam_id", sa.String(length=20)))
        if "steam_persona_name" not in user_columns:
            batch_op.add_column(sa.Column("steam_persona_name", sa.String(length=255)))

    op.create_table(
        "steam_library_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("steam_app_id", sa.Integer(), nullable=False),
        sa.Column("playtime_minutes", sa.Integer(), nullable=False),
        sa.Column("last_played_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "steam_app_id", name="unique_steam_library_entry"
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_steam_library_entries_rom_id",
        "steam_library_entries",
        ["rom_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("steam_library_entries", if_exists=True)

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("steam_persona_name", if_exists=True)
        batch_op.drop_column("steam_id", if_exists=True)

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("storefront", if_exists=True)
