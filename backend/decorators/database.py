import functools
import inspect
from collections.abc import Callable, Iterator
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from handler.database.base_handler import sync_session
from logger.logger import log

# Default for a `session` parameter that begin_session fills before the body runs.
INJECTED_SESSION = cast(Session, None)


def begin_session[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    if inspect.isgeneratorfunction(func):
        generator = _begin_generator_session(cast(Callable[P, Iterator[Any]], func))
        return cast(Callable[P, R], generator)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        # Reuse a caller-provided session so the handler can join an existing unit of work
        if kwargs.get("session") is not None:
            return func(*args, **kwargs)

        try:
            with sync_session.begin() as s:
                kwargs["session"] = s
                return func(*args, **kwargs)
        except ProgrammingError as exc:
            log.critical(str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
            ) from exc

    return wrapper


def _begin_generator_session[**P](
    func: Callable[P, Iterator[Any]],
) -> Callable[P, Iterator[Any]]:
    """begin_session for a generator, whose session must outlive the first call."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Iterator[Any]:
        if kwargs.get("session") is not None:
            yield from func(*args, **kwargs)
            return

        with sync_session.begin() as s:
            kwargs["session"] = s
            yield from func(*args, **kwargs)

    return wrapper
