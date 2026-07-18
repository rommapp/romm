"""Add client_tokens table for long-lived API tokens

Revision ID: 0072_client_tokens
Revises: 0071_sibling_roms_fs_name
Create Date: 2026-03-10 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0072_client_tokens"
down_revision = "0071_sibling_roms_fs_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("hashed_token", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.String(length=1000), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    with op.batch_alter_table("client_tokens") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_client_tokens_hashed_token"),
            ["hashed_token"],
            unique=True,
            if_not_exists=True,
        )
        batch_op.create_index(
            batch_op.f("ix_client_tokens_user_id"),
            ["user_id"],
            if_not_exists=True,
        )


def downgrade() -> None:
    op.drop_table("client_tokens", if_exists=True)
