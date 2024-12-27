"""empty message

Revision ID: 0014_asset_files
Revises: 0013_upgrade_file_extension
Create Date: 2024-02-08 15:03:26.338964

"""

import os

import sqlalchemy as sa
from alembic import op
from config import ROMM_DB_DRIVER
from config.config_manager import SQLITE_DB_BASE_PATH, ConfigManager
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker

# revision identifiers, used by Alembic.
revision = "0014_asset_files"
down_revision = "0013_upgrade_file_extension"
branch_labels = None
depends_on = None

SIZE_UNIT_TO_BYTES = {
    "B": 1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
    "TB": 1024**4,
    "PB": 1024**5,
}


def migrate_to_mysql() -> None:
    if ROMM_DB_DRIVER not in ("mariadb", "mysql"):
        raise Exception("Version 3.0 requires MariaDB or MySQL as database driver!")

    # Skip if sqlite database is not mounted
    if not os.path.exists(f"{SQLITE_DB_BASE_PATH}/romm.db"):
        return

    maria_engine = create_engine(ConfigManager.get_db_engine(), pool_pre_ping=True)
    maria_session = sessionmaker(bind=maria_engine, expire_on_commit=False)

    sqlite_engine = create_engine(
        f"sqlite:////{SQLITE_DB_BASE_PATH}/romm.db", pool_pre_ping=True
    )
    sqlite_session = sessionmaker(bind=sqlite_engine, expire_on_commit=False)

    # Copy all data from sqlite to maria
    with maria_session.begin() as maria_conn:
        with sqlite_session.begin() as sqlite_conn:
            maria_conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))

            tables = sqlite_conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table';")
            ).fetchall()
            for table_name in tables:
                table_name = table_name[0]

                # Skip migration for the 'alembic_version' table
                if table_name == "alembic_version":
                    continue

                table_data = sqlite_conn.execute(
                    text(f"SELECT * FROM {table_name}")  # nosec B608
                ).fetchall()

                # Insert data into MariaDB table
                for row in table_data:
                    mapped_row = {f"{i}": value for i, value in enumerate(row, start=1)}
                    columns = ",".join([f":{i}" for i in range(1, len(row) + 1)])
                    insert_query = (
                        f"INSERT INTO {table_name} VALUES ({columns})"  # nosec B608
                    )
                    maria_conn.execute(text(insert_query), mapped_row)

            maria_conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def upgrade() -> None:
    migrate_to_mysql()

    op.create_table(
        "saves",
        sa.Column("emulator", sa.String(length=50), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("file_name", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_tags", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_ext", sa.String(length=450), nullable=False),
        sa.Column("file_extension", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "screenshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("file_name", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_tags", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_ext", sa.String(length=450), nullable=False),
        sa.Column("file_extension", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "states",
        sa.Column("emulator", sa.String(length=50), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("file_name", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_tags", sa.String(length=450), nullable=False),
        sa.Column("file_name_no_ext", sa.String(length=450), nullable=False),
        sa.Column("file_extension", sa.String(length=100), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("rom_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["rom_id"], ["roms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Drop the constraint to platform slug
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_constraint("fk_platform_roms", type_="foreignkey")

    # Drop the primary key (slug)
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.drop_constraint(constraint_name="PRIMARY", type_="primary")
        batch_op.drop_column("n_roms")

    # Switch to new id column as platform primary key
    op.execute(
        "ALTER TABLE platforms ADD COLUMN id INTEGER(11) NOT NULL AUTO_INCREMENT PRIMARY KEY"
    )

    # Add new columns to roms table
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("file_name_no_ext", sa.String(length=450), nullable=False)
        )
        batch_op.add_column(
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=False)
        )
        batch_op.add_column(sa.Column("igdb_metadata", mysql.JSON(), nullable=True))
        batch_op.add_column(sa.Column("platform_id", sa.Integer(), nullable=False))
        batch_op.alter_column(
            "revision",
            existing_type=mysql.VARCHAR(length=20),
            type_=sa.String(length=100),
            existing_nullable=True,
        )

    # Move data around
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.execute("update roms set igdb_metadata = '\\{\\}'")
        batch_op.execute(
            "update roms set path_cover_s = '', path_cover_l = '', url_cover = '' where url_cover = 'https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png'"
        )
        batch_op.execute(
            "update roms set file_name_no_ext = regexp_replace(file_name, '\\.[a-z]{2,}$', '')"
        )
        batch_op.execute(
            "update roms inner join platforms on roms.platform_slug = platforms.slug set roms.platform_id = platforms.id"
        )

    # Process filesize data and prepare for bulk update
    connection = op.get_bind()
    result = connection.execute(text("SELECT id, file_size, file_size_units FROM roms"))
    updates = []
    for row in result:
        file_size_bytes = int(row[1] * SIZE_UNIT_TO_BYTES.get(row[2], 1))
        updates.append({"id": row[0], "file_size_bytes": file_size_bytes})

    if updates:
        # Perform bulk update
        connection.execute(
            text("UPDATE roms SET file_size_bytes = :file_size_bytes WHERE id = :id"),
            updates,
        )

    # Cleanup roms table
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_platform_id_roms",
            "platforms",
            ["platform_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_column("file_size")
        batch_op.drop_column("file_size_units")
        batch_op.drop_column("p_sgdb_id")
        batch_op.drop_column("p_name")
        batch_op.drop_column("p_igdb_id")
        batch_op.drop_column("platform_slug")


def downgrade() -> None:
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("platform_slug", mysql.VARCHAR(length=50), nullable=False)
        )
        batch_op.add_column(
            sa.Column("p_igdb_id", mysql.VARCHAR(length=10), nullable=True)
        )
        batch_op.add_column(
            sa.Column("p_name", mysql.VARCHAR(length=150), nullable=True)
        )
        batch_op.add_column(
            sa.Column("p_sgdb_id", mysql.VARCHAR(length=10), nullable=True)
        )
        batch_op.add_column(
            sa.Column("file_size_units", mysql.VARCHAR(length=10), nullable=False)
        )
        batch_op.add_column(sa.Column("file_size", mysql.FLOAT(), nullable=False))
        batch_op.drop_constraint("fk_platform_id_roms", type_="foreignkey")

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.create_foreign_key(
            "fk_platform_roms",
            "platforms",
            ["platform_slug"],
            ["slug"],
            ondelete="CASCADE",
        )
        batch_op.execute(
            "update roms inner join platforms on roms.platform_id = platforms.id set roms.platform_slug = platforms.slug"
        )
        batch_op.execute(
            "update roms set url_cover = 'https://images.igdb.com/igdb/image/upload/t_cover_big/nocover.png' where url_cover = ''"
        )

    # Process filesize data and prepare for bulk update
    connection = op.get_bind()
    result = connection.execute(text("SELECT id, file_size_bytes FROM roms"))

    updates = []
    for row in result:
        file_size = row[1] / SIZE_UNIT_TO_BYTES["MB"]
        updates.append({"id": row[0], "file_size": file_size, "file_size_units": "MB"})

    if updates:
        # Perform bulk update
        connection.execute(
            text(
                "UPDATE roms SET file_size = :file_size, file_size_units = :file_size_units WHERE id = :id"
            ),
            updates,
        )

    # Cleanup roms table
    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.drop_column("platform_id")
        batch_op.drop_column("igdb_metadata")
        batch_op.drop_column("file_size_bytes")
        batch_op.drop_column("file_name_no_ext")
        batch_op.alter_column(
            "revision",
            existing_type=sa.String(length=100),
            type_=mysql.VARCHAR(length=20),
            existing_nullable=True,
        )

    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "n_roms",
                mysql.INTEGER(display_width=11),
                autoincrement=False,
                nullable=True,
            )
        )
        batch_op.drop_column("id")

    op.drop_table("states")
    op.drop_table("screenshots")
    op.drop_table("saves")
