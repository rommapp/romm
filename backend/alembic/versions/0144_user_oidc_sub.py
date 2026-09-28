"""add oidc_issuer and oidc_sub to users

Revision ID: 0144_user_oidc_sub
Revises: 0143_sibling_platform_names
Create Date: 2026-09-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

from utils.database import exact_collation

# revision identifiers, used by Alembic.
revision = "0144_user_oidc_sub"
down_revision = "0143_sibling_platform_names"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_users_oidc_identity"


def upgrade() -> None:
    collation = exact_collation(op.get_bind())
    # Existing OIDC users are linked on their next login, matched by email.
    with op.batch_alter_table("users", schema=None) as batch_op:
        for column in ("oidc_issuer", "oidc_sub"):
            batch_op.add_column(
                sa.Column(
                    column,
                    sa.String(length=255, collation=collation),
                    nullable=True,
                ),
                if_not_exists=True,
            )
        batch_op.create_index(
            INDEX_NAME,
            ["oidc_issuer", "oidc_sub"],
            unique=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(INDEX_NAME, if_exists=True)
        batch_op.drop_column("oidc_sub", if_exists=True)
        batch_op.drop_column("oidc_issuer", if_exists=True)
