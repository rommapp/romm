"""add disc_file_id to states

Revision ID: 0110_state_disc_file
Revises: 0109_container_adoptions
Create Date: 2026-08-14 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0110_state_disc_file"
down_revision = "0109_container_adoptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.add_column(sa.Column("disc_file_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_states_disc_file_id",
            "rom_files",
            ["disc_file_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.drop_constraint("fk_states_disc_file_id", type_="foreignkey")
        batch_op.drop_column("disc_file_id")
