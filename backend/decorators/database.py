import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from handler.database.base_handler import sync_session
from logger.logger import log

# Default for a `session` parameter that begin_session fills before the body runs.
INJECTED_SESSION = cast(Session, None)

_current_session: ContextVar[Session | None] = ContextVar(
    "current_session", default=None
)


def in_transaction() -> bool:
    """Whether a transaction is open in the current context."""
    return _current_session.get() is not None


@contextmanager
def _ambient(session: Session) -> Iterator[Session]:
    token = _current_session.set(session)
    try:
        yield session
    finally:
        _current_session.reset(token)


@contextmanager
def _begin() -> Iterator[Session]:
    try:
        with sync_session.begin() as session, _ambient(session):
            yield session
    except ProgrammingError as exc:
        log.critical(str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc


@contextmanager
def transaction() -> Iterator[Session]:
    """Join the open transaction, or begin one that nested handler calls join."""
    current = _current_session.get()
    if current is not None:
        yield current
        return
    with _begin() as session:
        yield session


def _wrap[**P, R](func: Callable[P, R], *, isolated: bool) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        explicit = cast(Session | None, kwargs.get("session"))
        if explicit is not None:
            with _ambient(explicit):
                return func(*args, **kwargs)

        current = _current_session.get()
        if current is not None and not isolated:
            kwargs["session"] = current
            return func(*args, **kwargs)

        with _begin() as session:
            kwargs["session"] = session
            return func(*args, **kwargs)

    return wrapper


def begin_session[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Run in the caller's session, the open transaction, or a new one."""
    return _wrap(func, isolated=False)


def begin_isolated_session[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Run in a transaction of its own unless the caller passes a session."""
    return _wrap(func, isolated=True)
