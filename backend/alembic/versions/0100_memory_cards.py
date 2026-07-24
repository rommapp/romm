"""Add memory_cards and memory_card_versions tables

Revision ID: 0100_memory_cards
Revises: 0099_platform_description
Create Date: 2026-07-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0100_memory_cards"
down_revision = "0099_platform_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_cards",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("emulator", sa.String(length=50), nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("memory_cards") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_memory_cards_user_emulator"),
            ["user_id", "emulator"],
        )
        batch_op.create_index(
            batch_op.f("ix_memory_cards_public"),
            ["is_public"],
        )

    op.create_table(
        "memory_card_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("memory_card_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_tags", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_ext", sa.String(length=450), nullable=False),
        sa.Column("file_extension", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column(
            "file_size_bytes", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "missing_from_fs",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("content_hash", sa.String(length=32), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["memory_card_id"], ["memory_cards.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("memory_card_versions") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_memory_card_versions_card"),
            ["memory_card_id"],
        )
        batch_op.create_index(
            batch_op.f("ix_memory_card_versions_card_hash"),
            ["memory_card_id", "content_hash"],
        )


def downgrade() -> None:
    # drop_table removes the tables' indexes and foreign keys; dropping the
    # FK-backing indexes explicitly first is both redundant and rejected by
    # MariaDB/MySQL.
    op.drop_table("memory_card_versions")
    op.drop_table("memory_cards")
