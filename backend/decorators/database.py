import functools

from fastapi import HTTPException, status
from sqlalchemy.exc import ProgrammingError

from handler.database.base_handler import sync_session
from logger.logger import log


def begin_session(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
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
