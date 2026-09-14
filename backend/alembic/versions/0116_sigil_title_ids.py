"""Add the binary identity columns on roms: title_id, save_target and
save_target_layout.

Revision ID: 0116_sigil_title_ids
Revises: 0115_add_steam_metadata
Create Date: 2026-07-23 00:00:00.000000

"""

from alembic import op

from utils.roms_columns import drop_save_target_layout_type, ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0116_sigil_title_ids"
down_revision = "0115_add_steam_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ensure_roms_columns(op.get_bind())

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_index(
            "idx_roms_title_id",
            ["title_id"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_index("idx_roms_title_id", if_exists=True)
        batch_op.drop_column("save_target_layout", if_exists=True)
        batch_op.drop_column("save_target", if_exists=True)
        batch_op.drop_column("title_id", if_exists=True)

    drop_save_target_layout_type(op.get_bind())
