import functools

from fastapi import HTTPException, status
from handler.database.base_handler import sync_session
from logger.logger import log
from sqlalchemy.exc import ProgrammingError


def begin_session(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if hasattr(kwargs, "session"):
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
