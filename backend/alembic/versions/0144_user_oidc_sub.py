"""add oidc_sub to users

Revision ID: 0144_user_oidc_sub
Revises: 0143_sibling_platform_names
Create Date: 2026-09-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0144_user_oidc_sub"
down_revision = "0143_sibling_platform_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing OIDC users are linked on their next login, matched by email.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("oidc_sub", sa.String(length=255), nullable=True),
            if_not_exists=True,
        )
        batch_op.create_index(
            batch_op.f("ix_users_oidc_sub"),
            ["oidc_sub"],
            unique=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_oidc_sub"), if_exists=True)
        batch_op.drop_column("oidc_sub", if_exists=True)
