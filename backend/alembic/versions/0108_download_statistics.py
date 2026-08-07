"""Add download_events table and rom download counters

Revision ID: 0108_download_statistics
Revises: 0107_roms_dedup_cover_index
Create Date: 2026-07-29 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0108_download_statistics"
down_revision = "0107_roms_dedup_cover_index"
branch_labels = None
depends_on = None

DOWNLOAD_SOURCES = ("webui", "basic_auth", "client_token", "oauth", "anonymous")
DOWNLOAD_KINDS = ("rom", "file")


def upgrade() -> None:
    op.create_table(
        "download_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("rom_id", sa.Integer(), nullable=True),
        sa.Column("platform_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("rom_name", sa.String(length=450), nullable=False),
        sa.Column("platform_name", sa.String(length=400), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                *DOWNLOAD_SOURCES,
                native_enum=False,
                length=20,
                name="download_source",
            ),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.Enum(
                *DOWNLOAD_KINDS,
                native_enum=False,
                length=10,
                name="download_kind",
            ),
            nullable=False,
        ),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("downloaded_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("download_events") as batch_op:
        batch_op.create_index(
            "ix_download_events_rom_time",
            ["rom_id", "downloaded_at"],
        )
        batch_op.create_index(
            "ix_download_events_user_time",
            ["user_id", "downloaded_at"],
        )
        batch_op.create_index(
            "ix_download_events_time",
            ["downloaded_at"],
        )

    with op.batch_alter_table("roms") as batch_op:
        batch_op.add_column(
            sa.Column(
                "download_count",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_downloaded_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_roms_download_count",
            ["download_count"],
        )


def downgrade() -> None:
    with op.batch_alter_table("roms") as batch_op:
        batch_op.drop_index("ix_roms_download_count")
        batch_op.drop_column("last_downloaded_at")
        batch_op.drop_column("download_count")

    with op.batch_alter_table("download_events") as batch_op:
        batch_op.drop_index("ix_download_events_time")
        batch_op.drop_index("ix_download_events_user_time")
        batch_op.drop_index("ix_download_events_rom_time")
    op.drop_table("download_events")
