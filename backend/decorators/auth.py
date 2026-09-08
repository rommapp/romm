import functools
import inspect
from typing import Any

from authlib.integrations.starlette_client import OAuth
from authlib.oidc.discovery import get_well_known_url
from fastapi import HTTPException, Security, status
from fastapi.security.http import HTTPBasic
from fastapi.security.oauth2 import OAuth2PasswordBearer
from fastapi.types import DecoratedCallable
from starlette._utils import is_async_callable
from starlette.authentication import has_required_scope
from starlette.config import Config
from starlette.requests import Request

from config import (
    OIDC_CLAIM_ROLES,
    OIDC_CLIENT_ID,
    OIDC_CLIENT_SECRET,
    OIDC_ENABLED,
    OIDC_PROVIDER,
    OIDC_REDIRECT_URI,
    OIDC_SERVER_APPLICATION_URL,
    OIDC_SERVER_METADATA_URL,
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
    server_metadata_url=OIDC_SERVER_METADATA_URL
    or get_well_known_url(config.get("OIDC_SERVER_APPLICATION_URL"), external=True),
    client_kwargs={
        "scope": f"openid profile email {OIDC_CLAIM_ROLES}".strip(),
        "verify": OIDC_TLS_CACERTFILE,
        # Authlib only derives a code_verifier when code_challenge_method is set,
        # so providers that mandate PKCE refuse the code without it.
        "code_challenge_method": "S256",
    },
)


def _raise_auth_error(request: Request) -> None:
    """Raise the status matching the caller's auth state.

    401 tells the client it has no valid credentials (so it can redirect to
    login), while 403 means the authenticated user lacks the required scope
    (an inline permission error, not a session problem).
    """
    if not request.user.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _requires_scopes(scopes: list[Scope]):
    """Scope guard mirroring starlette's `requires`, with a 401/403 split."""

    def decorator(func: DecoratedCallable) -> DecoratedCallable:
        sig = inspect.signature(func)
        idx = next(
            (
                i
                for i, parameter in enumerate(sig.parameters.values())
                if parameter.name == "request"
            ),
            None,
        )
        if idx is None:
            raise Exception(f'No "request" argument on function "{func}"')

        if is_async_callable(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                request = kwargs.get("request", args[idx] if idx < len(args) else None)
                assert isinstance(request, Request)
                if not has_required_scope(request, scopes):
                    _raise_auth_error(request)
                return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            request = kwargs.get("request", args[idx] if idx < len(args) else None)
            assert isinstance(request, Request)
            if not has_required_scope(request, scopes):
                _raise_auth_error(request)
            return func(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def protected_route(
    method: Any,
    path: str,
    scopes: list[Scope] | None = None,
    **kwargs,
):
    def decorator(func: DecoratedCallable) -> DecoratedCallable:
        fn = _requires_scopes(scopes or [])(func)
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
