import logging
import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from config import DEV_SQL_ECHO
from config.config_manager import ConfigManager

sync_engine = create_engine(
    ConfigManager.get_db_engine(), pool_pre_ping=True, echo=False
)
sync_session = sessionmaker(bind=sync_engine, expire_on_commit=False)

# Disable SQLAlchemy logging as echo will print the queries
logging.getLogger("sqlalchemy.engine.Engine").handlers = [logging.NullHandler()]

_ROMS_CHANGED_KEY = "_roms_changed"


def mark_roms_changed(session) -> None:
    """Flag that a rom mutation happened so the materialized virtual_collections
    table is rebuilt after this session commits (issue #3768)."""
    session.info[_ROMS_CHANGED_KEY] = True


@event.listens_for(sync_session, "after_commit")
def _rebuild_virtual_collections_after_commit(session) -> None:
    if not session.info.pop(_ROMS_CHANGED_KEY, False):
        return
    # Imported lazily to avoid a circular import at module load
    # (tasks -> handlers -> base_handler).
    from tasks.manual.rebuild_virtual_collections import (
        enqueue_virtual_collections_rebuild,
    )

    enqueue_virtual_collections_rebuild()


if DEV_SQL_ECHO:

    @event.listens_for(sync_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        context._query_start_time = time.time()
        print("--------START--------")
        print(f"SQL: {statement}")
        print(f"Parameters: {parameters}")

    @event.listens_for(sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = time.time() - context._query_start_time
        print(f"Execution time: {total_time:.4f} seconds")
        print("--------END--------")


class DBBaseHandler: ...
