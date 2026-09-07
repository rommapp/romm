import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

from config.config_manager import ConfigManager
from logger.logger import unify_logger
from models.assets import (  # noqa
    MemoryCard,
    MemoryCardVersion,
    Save,
    Screenshot,
    State,
)
from models.base import BaseModel
from models.client_token import ClientToken  # noqa
from models.collection import VirtualCollection
from models.container_adoption import StreamingContainerAdoption  # noqa
from models.device import Device  # noqa
from models.device_save_sync import DeviceSaveSync  # noqa
from models.firmware import Firmware  # noqa
from models.music import MusicFavoriteTrack, MusicPlaylist, MusicPlaylistTrack  # noqa
from models.platform import Platform  # noqa
from models.play_session import PlaySession  # noqa
from models.rom import Rom, RomFacets, RomMetadata, SiblingRom  # noqa
from models.sync_session import SyncSession  # noqa
from models.user import User  # noqa
from utils.database import AUTOGENERATE_EXEMPT_INDEX_NAMES

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

unify_logger("alembic")

# add your model's MetaData object here
# for 'autogenerate' support
sys.path.append(f"{Path(__file__).parent.parent.resolve()}")

target_metadata = BaseModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


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

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
