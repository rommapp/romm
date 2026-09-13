import sys
from pathlib import Path

from alembic import context
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from sqlalchemy import create_engine
from sqlalchemy.exc import DatabaseError

from config.config_manager import ConfigManager
from logger.logger import unify_logger
from models import load_all_models
from models.base import BaseModel
from models.collection import VirtualCollection
from models.rom import RomMetadata, SiblingRom
from utils.database import (
    AUTOGENERATE_EXEMPT_INDEX_NAMES,
    is_binlog_trigger_privilege_error,
    trigger_ddl_is_blocked,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

unify_logger("alembic")

# add your model's MetaData object here
# for 'autogenerate' support
sys.path.append(f"{Path(__file__).parent.parent.resolve()}")

load_all_models()
target_metadata = BaseModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


# Several migrations keep the `roms_facets` and `virtual_collection_roms` mirrors
# in sync with triggers, which error 1419 denies outright (issue #3932).
TRIGGER_DDL_DENIED = (
    "The database user is not allowed to create triggers, which RomM's migrations "
    "need: MySQL and MariaDB deny trigger statements while binary logging is on "
    "and the user holds neither SUPER nor BINLOG ADMIN (error 1419). Ask an admin "
    "database user to set 'log_bin_trust_function_creators = 1' under [mysqld] in "
    "my.cnf, or to run GRANT BINLOG ADMIN ON *.* TO '<romm database user>'@'%', "
    "then start RomM again. See https://docs.romm.app/latest/install/databases/"
)


def has_pending_migrations() -> bool:
    """Whether any revision is still unapplied, so trigger DDL may yet run."""
    heads = ScriptDirectory.from_config(config).get_heads()
    return set(context.get_context().get_current_heads()) != set(heads)


# Ignore specific models when running migrations
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in [
        SiblingRom.__tablename__,
        VirtualCollection.__tablename__,
        RomMetadata.__tablename__,
    ]:  # Virtual table
        return False

    # Dialect-specific indexes that no model can declare.
    if type_ == "index" and name in AUTOGENERATE_EXEMPT_INDEX_NAMES:
        return False

    # generated_* are STORED generated columns backing views.
    # They are maintained in raw SQL (dialect-specific expressions) rather
    # than the ORM model, so hide them from autogenerate to avoid false drops.
    if type_ == "column" and name.startswith("generated_"):
        return False

    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """

    context.configure(
        url=ConfigManager.get_db_engine(),
        target_metadata=target_metadata,
        render_as_batch=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    engine = create_engine(ConfigManager.get_db_engine())

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            compare_type=True,
            include_object=include_object,
        )

        if has_pending_migrations() and trigger_ddl_is_blocked(connection):
            raise CommandError(TRIGGER_DDL_DENIED)

        with context.begin_transaction():
            try:
                context.run_migrations()
            except DatabaseError as exc:
                if is_binlog_trigger_privilege_error(exc):
                    raise CommandError(TRIGGER_DDL_DENIED) from exc
                raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
