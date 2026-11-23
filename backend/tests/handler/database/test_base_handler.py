import pytest

from handler.database.base_handler import read_committed, sync_engine


class _Cursor:
    def __init__(self, log_bin: int, binlog_format: str) -> None:
        self.row = (log_bin, binlog_format)
        self.executed: list[str] = []

    def execute(self, statement: str) -> None:
        self.executed.append(statement)

    def fetchone(self) -> tuple[int, str]:
        return self.row

    def close(self) -> None: ...


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor
        self.committed = False

    def cursor(self) -> _Cursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True


@pytest.mark.skipif(
    sync_engine.dialect.name not in ("mariadb", "mysql"),
    reason="PostgreSQL runs at READ COMMITTED by default",
)
def test_sessions_run_at_read_committed():
    with sync_engine.connect() as conn:
        assert conn.get_isolation_level() == "READ COMMITTED"


@pytest.mark.parametrize(
    ("log_bin", "binlog_format", "sets_it"),
    [
        (0, "STATEMENT", True),
        (1, "ROW", True),
        (1, "MIXED", True),
        (1, "STATEMENT", False),
    ],
)
def test_read_committed_unless_statement_binlog(
    log_bin: int, binlog_format: str, sets_it: bool
):
    cursor = _Cursor(log_bin, binlog_format)
    connection = _Connection(cursor)

    read_committed(connection, None)

    set_isolation = "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED"
    assert (set_isolation in cursor.executed) is sets_it
    assert connection.committed
