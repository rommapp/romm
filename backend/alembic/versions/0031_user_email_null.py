"""Change empty string in users.email to NULL.

Revision ID: 0031_user_email_null
Revises: 0030_screenscraper_data
Create Date: 2025-01-14 01:30:39.696257

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0031_user_email_null"
down_revision = "0030_screenscraper_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.execute("UPDATE users SET email = NULL WHERE email = ''")


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.execute("UPDATE users SET email = '' WHERE email IS NULL")
