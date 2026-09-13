"""The guard over MySQL and MariaDB denying trigger DDL under binary logging.

Error 1419 hits every trigger statement, `DROP TRIGGER IF EXISTS` included, so a
migration that installs a trigger cannot even clean up after itself (issue
#3932). `alembic/env.py` turns a denial into a message naming the fix.
"""

from unittest.mock import patch

import pytest
import sqlalchemy as sa

from handler.database.base_handler import sync_engine
from utils.database import (
    BINLOG_TRIGGER_DDL_ERRNO,
    is_binlog_trigger_privilege_error,
    is_mariadb,
    is_mysql,
    trigger_ddl_is_blocked,
)


class _DriverError(Exception):
    """A driver exception carrying the server error code, as both drivers do."""

    def __init__(self, errno: int):
        super().__init__(errno, "denied")
        self.errno = errno


class _CodelessDriverError(Exception):
    """A driver exception that only spells the code in `args`."""


def _wrap(orig: Exception) -> sa.exc.DatabaseError:
    return sa.exc.DatabaseError("DROP TRIGGER IF EXISTS t", None, orig)


def test_reads_the_code_through_the_sqlalchemy_wrapper():
    assert is_binlog_trigger_privilege_error(
        _wrap(_DriverError(BINLOG_TRIGGER_DDL_ERRNO))
    )


def test_falls_back_to_the_first_exception_argument():
    orig = _CodelessDriverError(BINLOG_TRIGGER_DDL_ERRNO, "denied")

    assert is_binlog_trigger_privilege_error(_wrap(orig))


@pytest.mark.parametrize("errno", [1045, 1146])
def test_leaves_every_other_database_error_alone(errno: int):
    assert not is_binlog_trigger_privilege_error(_wrap(_DriverError(errno)))


def test_an_exception_without_a_code_is_not_a_denial():
    assert not is_binlog_trigger_privilege_error(RuntimeError("boom"))


def test_a_server_that_allows_triggers_is_not_blocked():
    with sync_engine.connect() as conn:
        assert not trigger_ddl_is_blocked(conn)


def test_a_denied_probe_leaves_the_connection_usable():
    """The probe runs before the migrations, so it must not poison the session."""
    with sync_engine.connect() as conn:
        if not (is_mysql(conn) or is_mariadb(conn)):
            pytest.skip("only MySQL and MariaDB deny trigger DDL")

        denial = _wrap(_DriverError(BINLOG_TRIGGER_DDL_ERRNO))
        with patch.object(type(conn), "exec_driver_sql", side_effect=denial):
            assert trigger_ddl_is_blocked(conn)

        assert conn.scalar(sa.text("SELECT 1")) == 1
