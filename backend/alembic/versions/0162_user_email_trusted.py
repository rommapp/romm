"""add email_trusted to users

Revision ID: 0162_user_email_trusted
Revises: 0161_save_channels
Create Date: 2026-11-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0162_user_email_trusted"
down_revision = "0161_save_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing accounts keep linking by email as before; new ones start untrusted.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "email_trusted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            if_not_exists=True,
        )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "email_trusted",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=sa.false(),
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("email_trusted", if_exists=True)
