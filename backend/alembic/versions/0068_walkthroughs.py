"""Add walkthroughs table

Revision ID: 0068_walkthroughs
Revises: 0067_romfile_category_enum_cheat
Create Date: 2026-01-04 18:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "0068_walkthroughs"
down_revision: Union[str, None] = "0067_romfile_category_enum_cheat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "walkthroughs",
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("author", sa.String(length=250), nullable=True),
        sa.Column(
            "source",
            sa.Enum("GAMEFAQS", "UPLOAD", name="walkthroughsource"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column(
            "content",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["rom_id"],
            ["roms.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_walkthroughs_rom_id"), "walkthroughs", ["rom_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_walkthroughs_rom_id"), table_name="walkthroughs")
    op.drop_table("walkthroughs")
