"""empty message

Revision ID: 0018_increase_file_extension
Revises: 0017_file_name_no_ext
Create Date: 2024-01-27 13:00:54.042607

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0018_increase_file_extension"
down_revision = "0017_file_name_no_ext"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("saves", schema=None) as batch_op:
        batch_op.alter_column(
            "file_extension",
            existing_type=mysql.VARCHAR(length=10),
            type_=sa.String(length=100),
            existing_nullable=False,
        )

    with op.batch_alter_table("screenshots", schema=None) as batch_op:
        batch_op.alter_column(
            "file_extension",
            existing_type=mysql.VARCHAR(length=10),
            type_=sa.String(length=100),
            existing_nullable=False,
        )

    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.alter_column(
            "file_extension",
            existing_type=mysql.VARCHAR(length=10),
            type_=sa.String(length=100),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("states", schema=None) as batch_op:
        batch_op.alter_column(
            "file_extension",
            existing_type=sa.String(length=100),
            type_=mysql.VARCHAR(length=10),
            existing_nullable=False,
        )

    with op.batch_alter_table("screenshots", schema=None) as batch_op:
        batch_op.alter_column(
            "file_extension",
            existing_type=sa.String(length=100),
            type_=mysql.VARCHAR(length=10),
            existing_nullable=False,
        )

    with op.batch_alter_table("saves", schema=None) as batch_op:
        batch_op.alter_column(
            "file_extension",
            existing_type=sa.String(length=100),
            type_=mysql.VARCHAR(length=10),
            existing_nullable=False,
        )
