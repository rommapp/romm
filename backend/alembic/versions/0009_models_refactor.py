"""empty message

Revision ID: 0009_models_refactor
Revises: 2.0.0
Create Date: 2023-09-12 18:18:27.158732

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0009_models_refactor"
down_revision = "2.0.0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.alter_column(
            "igdb_id", existing_type=mysql.VARCHAR(length=10), nullable=True
        )
        batch_op.alter_column(
            "sgdb_id", existing_type=mysql.VARCHAR(length=10), nullable=True
        )
        batch_op.alter_column(
            "slug", existing_type=mysql.VARCHAR(length=50), nullable=False
        )
        batch_op.alter_column(
            "name", existing_type=mysql.VARCHAR(length=400), nullable=True
        )

    # Move primary key to slug
    try:
        op.drop_constraint(
            constraint_name="PRIMARY", table_name="platforms", type_="primary"
        )
        print("Dropped primary key on platforms table")
    except (ValueError, OperationalError) as e:
        print(f"Error dropping primary key on platforms table: {e}")

    try:
        op.create_primary_key(
            constraint_name=None, table_name="platforms", columns=["slug"]
        )
        print("Moved primary key to slug column on platforms table")
    except OperationalError as e:
        print(f"Error moving primary key to slug column on platforms table: {e}")

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "r_igdb_id",
            existing_type=mysql.VARCHAR(length=10),
            new_column_name="igdb_id",
        )
        batch_op.alter_column(
            "r_sgdb_id",
            existing_type=mysql.VARCHAR(length=10),
            new_column_name="sgdb_id",
        )
        batch_op.alter_column(
            "r_slug", existing_type=mysql.VARCHAR(length=400), new_column_name="slug"
        )
        batch_op.alter_column(
            "r_name", existing_type=mysql.VARCHAR(length=350), new_column_name="name"
        )
        batch_op.alter_column(
            "p_slug",
            existing_type=mysql.VARCHAR(length=50),
            new_column_name="platform_slug",
            nullable=False,
        )

        batch_op.alter_column(
            "file_extension", existing_type=mysql.VARCHAR(length=10), nullable=False
        )
        batch_op.alter_column(
            "file_path", existing_type=mysql.VARCHAR(length=1000), nullable=False
        )
        batch_op.alter_column("file_size", existing_type=mysql.FLOAT(), nullable=False)
        batch_op.alter_column(
            "file_size_units", existing_type=mysql.VARCHAR(length=10), nullable=False
        )
        batch_op.alter_column(
            "url_screenshots",
            existing_type=mysql.LONGTEXT(charset="utf8mb4", collation="utf8mb4_bin"),
            nullable=True,
            existing_server_default=sa.text("'[]'"),
        )
        batch_op.alter_column(
            "path_screenshots",
            existing_type=mysql.LONGTEXT(charset="utf8mb4", collation="utf8mb4_bin"),
            nullable=True,
            existing_server_default=sa.text("'[]'"),
        )

        batch_op.create_foreign_key(
            "fk_platform_roms", "platforms", ["platform_slug"], ["slug"]
        )


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.alter_column(
            "igdb_id",
            existing_type=mysql.VARCHAR(length=10),
            new_column_name="r_igdb_id",
        )
        batch_op.alter_column(
            "sgdb_id",
            existing_type=mysql.VARCHAR(length=10),
            new_column_name="r_sgdb_id",
        )
        batch_op.alter_column(
            "slug", existing_type=mysql.VARCHAR(length=400), new_column_name="r_slug"
        )
        batch_op.alter_column(
            "name", existing_type=mysql.VARCHAR(length=350), new_column_name="r_name"
        )
        batch_op.alter_column(
            "platform_slug",
            existing_type=mysql.VARCHAR(length=50),
            new_column_name="p_slug",
            nullable=True,
        )

        batch_op.alter_column(
            "path_screenshots",
            existing_type=mysql.LONGTEXT(charset="utf8mb4", collation="utf8mb4_bin"),
            nullable=False,
            existing_server_default=sa.text("'[]'"),
        )
        batch_op.alter_column(
            "url_screenshots",
            existing_type=mysql.LONGTEXT(charset="utf8mb4", collation="utf8mb4_bin"),
            nullable=False,
            existing_server_default=sa.text("'[]'"),
        )
        batch_op.alter_column(
            "file_size_units", existing_type=mysql.VARCHAR(length=10), nullable=True
        )
        batch_op.alter_column("file_size", existing_type=mysql.FLOAT(), nullable=True)
        batch_op.alter_column(
            "file_path", existing_type=mysql.VARCHAR(length=1000), nullable=True
        )
        batch_op.alter_column(
            "file_extension", existing_type=mysql.VARCHAR(length=10), nullable=True
        )

        batch_op.drop_constraint("fk_platform_roms", type_="foreignkey")

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.alter_column(
            "slug", existing_type=mysql.VARCHAR(length=50), nullable=True
        )

    # Move primary key to fs_slug
    try:
        op.drop_constraint(
            constraint_name="PRIMARY", table_name="platforms", type_="primary"
        )
        print("Dropped primary key on platforms table")
    except (ValueError, OperationalError) as e:
        print(f"Error dropping primary key on platforms table: {e}")

    try:
        op.create_primary_key(
            constraint_name=None, table_name="platforms", columns=["fs_slug"]
        )
        print("Moved primary key to fs_slug column on platforms table")
    except OperationalError as e:
        print(f"Error moving primary key to fs_slug column on platforms table: {e}")
