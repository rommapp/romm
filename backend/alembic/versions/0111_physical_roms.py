"""Add physical-game columns to roms.

`is_physical` and `upc` are declared in `utils.roms_columns`, which adds them in
the single table copy shared by every 5.3.0 revision that widens `roms`.

Revision ID: 0111_physical_roms
Revises: 0110_walkthrough_docs
Create Date: 2026-07-04 00:00:00.000000

"""

from alembic import op

from utils.roms_columns import ensure_roms_columns

# revision identifiers, used by Alembic.
revision = "0111_physical_roms"
down_revision = "0110_walkthrough_docs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    ensure_roms_columns(op.get_bind())


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("upc", if_exists=True)
        batch_op.drop_column("is_physical", if_exists=True)
