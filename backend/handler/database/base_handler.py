import logging
import time
from typing import Any, cast

from sqlalchemy import Connection, CursorResult, Result, create_engine, event
from sqlalchemy.orm import sessionmaker

from config import DB_POOL_RECYCLE_SECONDS, DEV_SQL_ECHO
from config.config_manager import ConfigManager

# A ping on a socket the server already closed blocks the worker until TCP gives
# up, so `pool_pre_ping` alone is not enough.
sync_engine = create_engine(
    ConfigManager.get_db_engine(),
    pool_pre_ping=True,
    pool_recycle=DB_POOL_RECYCLE_SECONDS,
    echo=False,
)
sync_session = sessionmaker(bind=sync_engine, expire_on_commit=False)

# Disable SQLAlchemy logging as echo will print the queries
logging.getLogger("sqlalchemy.engine.Engine").handlers = [logging.NullHandler()]


if DEV_SQL_ECHO:

    @event.listens_for(sync_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        context._query_start_time = time.time()
        print("--------START--------")
        print(f"SQL: {statement}")
        print(f"Parameters: {parameters}")

    @event.listens_for(sync_engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        total_time = time.time() - context._query_start_time
        print(f"Execution time: {total_time:.4f} seconds")
        print("--------END--------")


class DBBaseHandler: ...


def affected_rows(result: Result[Any]) -> int:
    """How many rows an UPDATE or DELETE run through `Session.execute` matched."""
    # Session.execute is typed to return Result, but DML gets a CursorResult.
    return cast(CursorResult[Any], result).rowcount
