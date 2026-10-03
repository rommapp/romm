import re
from collections.abc import Iterator, Sequence

import pytest
from sqlalchemy import Connection, create_engine, event, text
from tests.conftest import (
    _alembic_version,
    _clear_tables,
    _copy_schema,
    _recreate_database,
    engine,
    session,
)

from config import ROMM_DB_DRIVER
from models.platform import Platform

_AUTO_INCREMENT_RE = re.compile(r" AUTO_INCREMENT=\d+")
_DEFINER_RE = re.compile(r"\s+DEFINER=\S+")


def _snapshot(conn: Connection, schema: str) -> dict[str, object]:
    """Every table, view and trigger definition of `schema`, plus each table's rows."""
    objects = conn.execute(
        text(
            "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.TABLES"
            " WHERE TABLE_SCHEMA = :s ORDER BY TABLE_NAME"
        ),
        {"s": schema},
    ).all()
    triggers: Sequence[str] = (
        conn.execute(
            text(
                "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS"
                " WHERE TRIGGER_SCHEMA = :s ORDER BY TRIGGER_NAME"
            ),
            {"s": schema},
        )
        .scalars()
        .all()
    )
    conn.exec_driver_sql(f"USE `{schema}`")
    snapshot: dict[str, object] = {}
    for name, kind in objects:
        if kind == "VIEW":
            ddl = conn.exec_driver_sql(f"SHOW CREATE VIEW `{name}`").one()[1]
            snapshot[name] = _DEFINER_RE.sub("", ddl)
            continue
        ddl = conn.exec_driver_sql(f"SHOW CREATE TABLE `{name}`").one()[1]
        rows = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{name}`").scalar()
        checksum = conn.exec_driver_sql(f"CHECKSUM TABLE `{name}`").one()[1]
        snapshot[name] = (_AUTO_INCREMENT_RE.sub("", ddl), rows, checksum)
    for name in triggers:
        ddl = conn.exec_driver_sql(f"SHOW CREATE TRIGGER `{name}`").one()[2]
        snapshot[f"trigger:{name}"] = _DEFINER_RE.sub("", ddl)
    return snapshot


@pytest.fixture
def scratch_connection() -> Iterator[Connection]:
    # A private engine, since `_copy_schema` switches the connection's schema.
    scratch_engine = create_engine(engine.url)
    try:
        with scratch_engine.connect() as conn:
            yield conn
    finally:
        scratch_engine.dispose()


@pytest.mark.skipif(
    ROMM_DB_DRIVER not in ("mariadb", "mysql"),
    reason="the template clone only runs on MariaDB",
)
def test_copy_schema_reproduces_the_migrated_database(
    scratch_connection: Connection, platform: Platform
) -> None:
    source = engine.url.database
    assert source
    target = f"{source}_copy"
    _recreate_database(scratch_connection, target)
    try:
        _copy_schema(scratch_connection, source, target)

        assert _alembic_version(scratch_connection, target) == _alembic_version(
            scratch_connection, source
        )
        assert _snapshot(scratch_connection, target) == _snapshot(
            scratch_connection, source
        )
    finally:
        scratch_connection.exec_driver_sql(f"DROP DATABASE IF EXISTS `{target}`")


def test_clear_tables_deletes_only_from_tables_with_rows(platform: Platform) -> None:
    statements: list[str] = []

    def before_execute(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_execute)
    try:
        _clear_tables()
        _clear_tables()
    finally:
        event.remove(engine, "before_cursor_execute", before_execute)

    deletes = [s for s in statements if s.lstrip().upper().startswith("DELETE")]
    assert len(deletes) == 1
    assert Platform.__tablename__ in deletes[0]
    with session() as s:
        assert s.query(Platform).count() == 0
