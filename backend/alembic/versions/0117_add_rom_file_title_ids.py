"""Add the per-file title id columns on rom_files: title_id and title_version.

Rom-level title_id landed in 0116_sigil_title_ids; these columns hold the
identity of every file in a multi-part rom, extracted by rom-converto.

Revision ID: 0117_add_rom_file_title_ids
Revises: 0116_sigil_title_ids
Create Date: 2026-09-03 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op  # type: ignore[attr-defined]

# revision identifiers, used by Alembic.
revision = "0117_add_rom_file_title_ids"
down_revision = "0116_sigil_title_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rom_files",
        sa.Column("title_id", sa.String(length=100), nullable=True),
    )
    # BigInteger: Switch title versions are u32 and can exceed signed int32.
    op.add_column(
        "rom_files",
        sa.Column("title_version", sa.BigInteger(), nullable=True),
    )
    op.create_index("idx_rom_files_title_id", "rom_files", ["title_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_rom_files_title_id", table_name="rom_files")
    op.drop_column("rom_files", "title_version")
    op.drop_column("rom_files", "title_id")
