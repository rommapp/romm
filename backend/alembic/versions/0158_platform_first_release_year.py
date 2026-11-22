"""Store the original platform launch year."""

import sqlalchemy as sa
from alembic import op

from utils.database import column_names

revision = "0158_platform_first_release_year"
down_revision = "0157_rom_custom_sort_key_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "first_release_year" not in column_names(op.get_bind(), "platforms"):
        op.add_column(
            "platforms", sa.Column("first_release_year", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    op.drop_column("platforms", "first_release_year", if_exists=True)
