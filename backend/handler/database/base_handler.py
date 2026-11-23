import functools
import logging
import time
from typing import Any, cast

from sqlalchemy import Connection, CursorResult, Result, create_engine, event
from sqlalchemy.orm import sessionmaker

from config import DB_POOL_RECYCLE_SECONDS, DEV_SQL_ECHO
from config.config_manager import ConfigManager
from logger.logger import log
from models import load_all_models

# A ping on a socket the server already closed blocks the worker until TCP gives
# up, so `pool_pre_ping` alone is not enough.
sync_engine = create_engine(
    ConfigManager.get_db_engine(),
    pool_pre_ping=True,
    pool_recycle=DB_POOL_RECYCLE_SECONDS,
    echo=False,
)
sync_session = sessionmaker(bind=sync_engine, expire_on_commit=False)


@functools.cache
def _warn_statement_binlog() -> None:
    log.warning(
        "binlog_format is STATEMENT, so database sessions stay at REPEATABLE READ; "
        "concurrent writes may fail with 'Record has changed since last read'"
    )


def read_committed(dbapi_connection: Any, connection_record: Any) -> None:
    """Run the session at READ COMMITTED, unless statement binary logging forbids it."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SELECT @@log_bin, @@binlog_format")
        log_bin, binlog_format = cursor.fetchone()
        # InnoDB refuses every write below REPEATABLE READ under STATEMENT logging.
        if log_bin and binlog_format == "STATEMENT":
            _warn_statement_binlog()
        else:
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
    finally:
        cursor.close()
    dbapi_connection.commit()


# MariaDB 11.6+ at REPEATABLE READ fails a write to a row the transaction read
# before another one committed to it (error 1020). PostgreSQL defaults to this.
if sync_engine.dialect.name in ("mariadb", "mysql"):
    event.listen(sync_engine, "connect", read_committed)

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


def affected_rows(result: Result[*tuple[Any, ...]]) -> int:
    """How many rows an UPDATE or DELETE run through `Session.execute` matched."""
    # Session.execute is typed to return Result, but DML gets a CursorResult.
    return cast(CursorResult[*tuple[Any, ...]], result).rowcount


# A process may load one model, whose relationships name others by string, and
# the mappers configure only once every one of them is loaded.
load_all_models()
