"""Database race stubs shared by tests of concurrent writes."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy import event

from handler.database.base_handler import sync_engine


@contextmanager
def run_before_first(
    prefix: str, competitor: Callable[[], object]
) -> Iterator[list[str]]:
    """Run `competitor` once, just before the first statement starting with `prefix`.

    Yields the statements that triggered it, so a test can assert the race happened.
    """
    raced: list[str] = []

    def before_execute(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if raced or not statement.lstrip().lower().startswith(prefix):
            return
        raced.append(statement)
        competitor()

    event.listen(sync_engine, "before_cursor_execute", before_execute)
    try:
        yield raced
    finally:
        event.remove(sync_engine, "before_cursor_execute", before_execute)
