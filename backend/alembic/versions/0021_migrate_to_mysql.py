"""empty message

Revision ID: 0021_migrate_to_mysql
Revises: 0020_assets_user_id
Create Date: 2024-01-24 13:54:32.458301

"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config import ROMM_DB_DRIVER
from config.config_manager import ConfigManager, SQLITE_DB_BASE_PATH


# revision identifiers, used by Alembic.
revision = '0021_migrate_to_mysql'
down_revision = '0020_assets_user_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if ROMM_DB_DRIVER != "mariadb":
        raise Exception("Version 3.0 requires MariaDB as database driver!")
    
    # Skip if sqlite database is not mounted
    if not os.path.exists(f"{SQLITE_DB_BASE_PATH}/romm.db"):
        return
    
    maria_engine = create_engine(ConfigManager.get_db_engine(), pool_pre_ping=True)
    maria_session = sessionmaker(bind=maria_engine, expire_on_commit=False)

    sqlite_engine = create_engine(f"sqlite:////{SQLITE_DB_BASE_PATH}/romm.db", pool_pre_ping=True)
    sqlite_session = sessionmaker(bind=sqlite_engine, expire_on_commit=False)

    # Copy all data from sqlite to maria
    with maria_session.begin() as maria_conn:
        with sqlite_session.begin() as sqlite_conn:
            maria_conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))

            tables = sqlite_conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
            for table_name in tables:
                table_name = table_name[0]
                if table_name == "alembic_version":
                    continue

                table_data = sqlite_conn.execute(text(f"SELECT * FROM {table_name}")).fetchall()

                # Insert data into MariaDB table
                for row in table_data:
                    maria_conn.execute(text(f"INSERT INTO {table_name} VALUES {tuple(row)}"))

            maria_conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))


def downgrade() -> None:
    pass
