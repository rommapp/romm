"""platforms_custom_name

Revision ID: 0029_platforms_custom_name
Revises: 0028_user_email
Create Date: 2024-12-24 01:32:57.121432

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0029_platforms_custom_name"
down_revision = "0028_user_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("custom_name", sa.String(length=400), nullable=True),
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_column("custom_name", if_exists=True)
