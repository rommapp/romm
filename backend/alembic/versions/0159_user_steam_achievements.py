"""Add the user's Steam ID and achievement progression

Revision ID: 0159_user_steam_achievements
Revises: 0158_platform_first_release_year
Create Date: 2026-11-02 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import CustomJSON

# revision identifiers, used by Alembic.
revision = "0159_user_steam_achievements"
down_revision = "0158_platform_first_release_year"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("steam_id", sa.String(length=17), nullable=True),
            if_not_exists=True,
        )
        batch_op.add_column(
            sa.Column("steam_progression", CustomJSON(), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("steam_progression", if_exists=True)
        batch_op.drop_column("steam_id", if_exists=True)
