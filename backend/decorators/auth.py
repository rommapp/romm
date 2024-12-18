from typing import Any

from authlib.integrations.starlette_client import OAuth
from config import (
    OIDC_CLIENT_ID,
    OIDC_CLIENT_SECRET,
    OIDC_ENABLED,
    OIDC_REDIRECT_URI,
    OIDC_SERVER_APPLICATION_URL,
)
from fastapi import Security
from fastapi.security.http import HTTPBasic
from fastapi.security.oauth2 import OAuth2PasswordBearer
from fastapi.types import DecoratedCallable
from handler.auth.base_handler import (
    DEFAULT_SCOPES_MAP,
    FULL_SCOPES_MAP,
    WRITE_SCOPES_MAP,
    Scope,
)
from starlette.authentication import requires
from starlette.config import Config

# Using the internal password flow
oauth2_password_bearer = OAuth2PasswordBearer(
    tokenUrl="/token",
    auto_error=False,
    scopes={
        **DEFAULT_SCOPES_MAP,
        **WRITE_SCOPES_MAP,
        **FULL_SCOPES_MAP,
    },
)

# Using an OIDC authorization code flow
config = Config(
    environ={
        "OIDC_ENABLED": str(OIDC_ENABLED),
        "OIDC_CLIENT_ID": OIDC_CLIENT_ID,
        "OIDC_CLIENT_SECRET": OIDC_CLIENT_SECRET,
        "OIDC_REDIRECT_URI": OIDC_REDIRECT_URI,
        "OIDC_SERVER_APPLICATION_URL": OIDC_SERVER_APPLICATION_URL,
    }
)
oauth = OAuth(config=config)
oauth.register(
    name="openid",
    client_id=config.get("OIDC_CLIENT_ID"),
    client_secret=config.get("OIDC_CLIENT_SECRET"),
    server_metadata_url=f'{config.get("OIDC_SERVER_APPLICATION_URL")}/.well-known/openid-configuration',
    client_kwargs={"scope": "openid profile email"},
)


def protected_route(
    method: Any,
    path: str,
    scopes: list[Scope] | None = None,
    **kwargs,
):
    def decorator(func: DecoratedCallable) -> DecoratedCallable:
        fn = requires(scopes or [])(func)
        return method(
            path,
            dependencies=[
                Security(
                    dependency=oauth2_password_bearer,
                    scopes=scopes or [],
                ),
                Security(dependency=HTTPBasic(auto_error=False)),
            ],
            **kwargs,
        )(fn)

    return decorator
