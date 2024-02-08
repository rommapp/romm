"""empty message

Revision ID: 0014_asset_files
Revises: 0013_upgrade_file_extension
Create Date: 2024-02-08 15:03:26.338964

"""
import os
from alembic import op
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import sessionmaker
from config import ROMM_DB_DRIVER
from config.config_manager import SQLITE_DB_BASE_PATH, ConfigManager

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
    if ROMM_DB_DRIVER != "mariadb":
        raise Exception("Version 3.0 requires MariaDB as database driver!")

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
                if table_name == "alembic_version":
                    continue

                table_data = sqlite_conn.execute(
                    text(f"SELECT * FROM {table_name}")
                ).fetchall()

                # Insert data into MariaDB table
                if table_name == "roms":
                    for row in table_data:
                        summary = tuple(row)[15].replace('"', '\\"').replace("'", "\\'")
                        maria_conn.execute(
                            text(
                                f'INSERT INTO {table_name} (id, igdb_id, p_igdb_id, sgdb_id, p_sgdb_id, platform_slug, p_name, file_name, file_name_no_tags, file_extension, file_path, file_size, file_size_units, name, slug, summary, path_cover_s, path_cover_l, revision, tags, multi, files, url_cover, url_screenshots, path_screenshots, regions, languages) VALUES ({tuple(row)[0]}, {tuple(row)[1]}, "{tuple(row)[2]}", {tuple(row)[3]}, "{tuple(row)[4]}", "{tuple(row)[5]}", "{tuple(row)[6]}", "{tuple(row)[7]}", "{tuple(row)[8]}", "{tuple(row)[9]}", "{tuple(row)[10]}", {tuple(row)[11]}, "{tuple(row)[12]}", "{tuple(row)[13]}", "{tuple(row)[14]}", "{summary}", "{tuple(row)[16]}", "{tuple(row)[17]}", "{tuple(row)[18]}", \'{tuple(row)[19]}\', {tuple(row)[20]}, \'{tuple(row)[21]}\', "{tuple(row)[22]}", \'{tuple(row)[23]}\', \'{tuple(row)[24]}\', \'{tuple(row)[25]}\', \'{tuple(row)[26]}\')'.replace(
                                    "None,", "null,"
                                )
                            )
                        )
                else:
                    for row in table_data:
                        maria_conn.execute(
                            text(
                                f"INSERT INTO {table_name} VALUES {tuple(row)}".replace(
                                    "None,", "null,"
                                )
                            )
                        )

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
    with op.batch_alter_table("platforms", schema=None) as batch_op:
        batch_op.execute(
            "ALTER TABLE platforms ADD COLUMN id INTEGER(11) NOT NULL AUTO_INCREMENT PRIMARY KEY"
        )
        batch_op.drop_column("n_roms")

    with op.batch_alter_table("roms", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("file_name_no_ext", sa.String(length=450), nullable=False)
        )
        batch_op.add_column(
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=False)
        )
        batch_op.add_column(sa.Column("igdb_metadata", mysql.JSON(), nullable=True))
        batch_op.add_column(sa.Column("platform_id", sa.Integer(), nullable=False))
        batch_op.drop_constraint("fk_platform_roms", type_="foreignkey")
        batch_op.execute(
            "update roms inner join platforms on roms.platform_slug = platforms.slug set roms.platform_id = platforms.id"
        )
        batch_op.create_foreign_key(
            None, "platforms", ["platform_id"], ["id"], ondelete="CASCADE"
        )

    # Set file_name_no_ext on existing roms
    op.execute(
        "UPDATE roms SET file_name_no_ext = regexp_replace(file_name, '\\.[a-z]{2,}$', '')"
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
        batch_op.drop_constraint(None, type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_platform_roms", "platforms", ["platform_slug"], ["slug"]
        )

    op.execute(
        "update roms inner join platforms on roms.platform_id = platforms.id set roms.platform_slug = platforms.slug"
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
