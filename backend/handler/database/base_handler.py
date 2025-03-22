import time

from config import DEV_MODE
from config.config_manager import ConfigManager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sync_engine = create_engine(
    ConfigManager.get_db_engine(), pool_pre_ping=True, echo=DEV_MODE
)
sync_session = sessionmaker(bind=sync_engine, expire_on_commit=False)


if DEV_MODE:

    @event.listens_for(sync_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        context._query_start_time = time.time()
        print(f"SQL: {statement}")
        print(f"Parameters: {parameters}")

    @event.listens_for(sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total_time = time.time() - context._query_start_time
        print(f"Execution time: {total_time:.4f} seconds")


class DBBaseHandler: ...
