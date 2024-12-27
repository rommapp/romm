"""empty message

Revision ID: 0009_models_refactor
Revises: 2.0.0
Create Date: 2023-09-12 18:18:27.158732

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import OperationalError

# revision identifiers, used by Alembic.
revision = "0009_models_refactor"
down_revision = "2.0.0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    try:
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
            batch_op.drop_constraint(constraint_name="PRIMARY", type_="primary")
            batch_op.create_primary_key(constraint_name=None, columns=["slug"])
    except ValueError as e:
        print(f"Cannot drop primary key on platforms table: {e}")
    except OperationalError as e:
        print(f"Cannot move primary key to slug column on platforms table: {e}")

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
            existing_server_default=sa.text("(JSON_ARRAY())"),
        )
        batch_op.alter_column(
            "path_screenshots",
            existing_type=mysql.LONGTEXT(charset="utf8mb4", collation="utf8mb4_bin"),
            nullable=True,
            existing_server_default=sa.text("(JSON_ARRAY())"),
        )

    try:
        with op.batch_alter_table("roms", schema=None) as batch_op:
            batch_op.create_foreign_key(
                "fk_platform_roms", "platforms", ["platform_slug"], ["slug"]
            )
    except ValueError as e:
        print(f"Cannot create foreign key on roms table: {e}")


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
            existing_server_default=sa.text("(JSON_ARRAY())"),
        )
        batch_op.alter_column(
            "url_screenshots",
            existing_type=mysql.LONGTEXT(charset="utf8mb4", collation="utf8mb4_bin"),
            nullable=False,
            existing_server_default=sa.text("(JSON_ARRAY())"),
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

    try:
        with op.batch_alter_table("roms", schema=None) as batch_op:
            batch_op.drop_constraint("fk_platform_roms", type_="foreignkey")
    except ValueError as e:
        print(f"Cannot drop foreign key on roms table: {e}")
    else:
        print("Dropped foreign key on roms table")

    try:
        with op.batch_alter_table("platforms", schema=None) as batch_op:
            batch_op.alter_column(
                "slug", existing_type=mysql.VARCHAR(length=50), nullable=True
            )

            # Move primary key back to fs_slug
            batch_op.drop_constraint(constraint_name="PRIMARY", type_="primary")
            batch_op.create_primary_key(constraint_name=None, columns=["fs_slug"])
            print("Moved primary key back to fs_slug column on platforms table")
    except ValueError as e:
        print(f"Cannot drop primary key on platforms table: {e}")
    except OperationalError as e:
        print(f"Cannot move primary key to slug column on platforms table: {e}")
