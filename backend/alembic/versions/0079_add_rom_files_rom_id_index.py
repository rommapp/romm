"""Add index on rom_id for rom_files table

Revision ID: 0079_add_rom_files_rom_id_index
Revises: 0078_add_libretro_id_to_roms
Create Date: 2026-04-14 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0079_add_rom_files_rom_id_index"
down_revision = "0078_add_libretro_id_to_roms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.create_index(
            "idx_rom_files_rom_id",
            ["rom_id"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("rom_files", schema=None) as batch_op:
        batch_op.drop_index("idx_rom_files_rom_id", if_exists=True)
