from typing import Any

from authlib.integrations.starlette_client import OAuth
from config import (
    OAUTH_CLIENT_ID,
    OAUTH_CLIENT_SECRET,
    OAUTH_ENABLED,
    OAUTH_REDIRECT_URI,
    OAUTH_SERVER_METADATA_URL,
)
from fastapi import Depends, Security
from fastapi.security.http import HTTPBasic
from fastapi.security.oauth2 import OAuth2AuthorizationCodeBearer, OAuth2PasswordBearer
from fastapi.types import DecoratedCallable
from handler.auth.base_handler import (
    DEFAULT_SCOPES_MAP,
    FULL_SCOPES_MAP,
    WRITE_SCOPES_MAP,
    Scope,
)
from starlette.authentication import requires
from starlette.config import Config

oauth2_password_bearer = OAuth2PasswordBearer(
    tokenUrl="/token",
    auto_error=False,
    scopes={
        **DEFAULT_SCOPES_MAP,
        **WRITE_SCOPES_MAP,
        **FULL_SCOPES_MAP,
    },
)

config = Config(
    environ={
        "OAUTH_ENABLED": OAUTH_ENABLED,
        "OAUTH_CLIENT_ID": OAUTH_CLIENT_ID,
        "OAUTH_CLIENT_SECRET": OAUTH_CLIENT_SECRET,
        "OAUTH_REDIRECT_URI": OAUTH_REDIRECT_URI,
        "OAUTH_SERVER_METADATA_URL": OAUTH_SERVER_METADATA_URL,
    }
)
oauth = OAuth(config=config)
oauth.register(
    name="openid",
    client_id=config.get("OAUTH_CLIENT_ID"),
    client_secret=config.get("OAUTH_CLIENT_SECRET"),
    server_metadata_url=config.get("OAUTH_SERVER_METADATA_URL"),
    client_kwargs={"scope": "openid profile email"},
)

oauth2_autorization_code_bearer = OAuth2AuthorizationCodeBearer(
    authorizationUrl="/auth/openid",
    tokenUrl="/token",
)


def protected_route(
    method: Any,
    path: str,
    scopes: list[Scope] | None = None,
    **kwargs,
):
    def decorator(func: DecoratedCallable):
        fn = requires(scopes or [])(func)
        return method(
            path,
            dependencies=[
                Security(
                    dependency=oauth2_password_bearer,
                    scopes=scopes or [],
                ),
                Security(dependency=HTTPBasic(auto_error=False)),
                (
                    Security(
                        dependency=oauth2_autorization_code_bearer, scopes=scopes or []
                    )
                    if OAUTH_ENABLED
                    else Depends(lambda: None)
                ),
            ],
            **kwargs,
        )(fn)

    return decorator
