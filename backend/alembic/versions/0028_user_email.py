"""empty message

Revision ID: 0028_user_email
Revises: 0027_platforms_data
Create Date: 2024-12-09 19:26:34.257411

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0028_user_email"
down_revision = "0027_platforms_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_email"))
        batch_op.drop_column("email")
