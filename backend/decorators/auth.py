from typing import Any

from fastapi import Security
from fastapi.security.http import HTTPBasic
from fastapi.security.oauth2 import OAuth2PasswordBearer
from fastapi.types import DecoratedCallable
from handler.auth_handler import DEFAULT_SCOPES_MAP, FULL_SCOPES_MAP, WRITE_SCOPES_MAP
from starlette.authentication import requires

oauth2_password_bearer = OAuth2PasswordBearer(
    tokenUrl="/token",
    auto_error=False,
    scopes={
        **DEFAULT_SCOPES_MAP,
        **WRITE_SCOPES_MAP,
        **FULL_SCOPES_MAP,
    },
)


def protected_route(
    method: Any,
    path: str,
    scopes: list[str] = [],
    **kwargs,
):
    def decorator(func: DecoratedCallable):
        fn = requires(scopes)(func)
        return method(
            path,
            dependencies=[
                Security(
                    dependency=oauth2_password_bearer,
                    scopes=scopes,
                ),
                Security(dependency=HTTPBasic(auto_error=False)),
            ],
            **kwargs,
        )(fn)

    return decorator
