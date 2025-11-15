from typing import Any

from authlib.integrations.starlette_client import OAuth
from authlib.oidc.discovery import get_well_known_url
from fastapi import Security
from fastapi.security.http import HTTPBasic
from fastapi.security.oauth2 import OAuth2PasswordBearer
from fastapi.types import DecoratedCallable
from starlette.authentication import requires
from starlette.config import Config

from config import (
    OIDC_CLAIM_ROLES,
    OIDC_CLIENT_ID,
    OIDC_CLIENT_SECRET,
    OIDC_ENABLED,
    OIDC_PROVIDER,
    OIDC_REDIRECT_URI,
    OIDC_SERVER_APPLICATION_URL,
    OIDC_TLS_CACERTFILE,
)
from handler.auth.constants import (
    EDIT_SCOPES_MAP,
    FULL_SCOPES_MAP,
    READ_SCOPES_MAP,
    WRITE_SCOPES_MAP,
    Scope,
)

# Using the internal password flow
oauth2_password_bearer = OAuth2PasswordBearer(
    tokenUrl="/token",
    auto_error=False,
    scopes={
        **READ_SCOPES_MAP,
        **WRITE_SCOPES_MAP,
        **EDIT_SCOPES_MAP,
        **FULL_SCOPES_MAP,
    },
)

# Using an OIDC authorization code flow
config = Config(
    environ={
        "OIDC_ENABLED": str(OIDC_ENABLED),
        "OIDC_PROVIDER": OIDC_PROVIDER,
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
    server_metadata_url=get_well_known_url(
        config.get("OIDC_SERVER_APPLICATION_URL"), external=True
    ),
    client_kwargs={
        "scope": f"openid profile email {OIDC_CLAIM_ROLES}".strip(),
        "verify": OIDC_TLS_CACERTFILE,
    },
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
