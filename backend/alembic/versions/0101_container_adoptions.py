"""Add streaming_container_adoptions table

Revision ID: 0101_container_adoptions
Revises: 0100_memory_cards
Create Date: 2026-07-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0101_container_adoptions"
down_revision = "0100_memory_cards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "streaming_container_adoptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("container_key", sa.String(length=512), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "decided_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
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
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("container_key"),
    )


def downgrade() -> None:
    op.drop_table("streaming_container_adoptions")
