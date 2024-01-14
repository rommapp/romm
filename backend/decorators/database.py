import functools

from fastapi import HTTPException, status
from logger.logger import log
from sqlalchemy.exc import ProgrammingError


def begin_session(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if hasattr(kwargs, "session"):
            return func(*args, **kwargs)

        try:
            with args[0].session.begin() as s:
                return func(*args, **kwargs, session=s)
        except ProgrammingError as e:
            log.critical(str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )

    return wrapper
