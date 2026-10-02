"""Store the user's sealed RetroAchievements login for streaming sessions

Revision ID: 0147_users_ra_login
Revises: 0146_roms_search_aliases
Create Date: 2026-10-01 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0147_users_ra_login"
down_revision = "0146_roms_search_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sealed with utils.secret_box, so the column is plain text, not a URL or
    # a name, and carries no collation.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("ra_login_sealed", sa.Text(), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("ra_login_sealed", if_exists=True)
