import hashlib
from base64 import urlsafe_b64encode
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import APIRouter, Request
from fastapi.routing import APIRoute

from decorators.auth import oauth, protected_route
from handler.auth.constants import Scope


def _s256(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def test_oidc_client_is_configured_for_pkce():
    """Authlib only derives a code_verifier when this kwarg is set."""
    assert oauth.openid.client_kwargs["code_challenge_method"] == "S256"


@pytest.mark.asyncio
async def test_authorize_redirect_sends_a_challenge_matching_the_stored_verifier(
    monkeypatch,
):
    """The callback can only redeem the code if these two halves agree."""
    monkeypatch.setitem(
        oauth.openid.server_metadata,
        "authorization_endpoint",
        "https://idp.example.com/authorize",
    )
    monkeypatch.setitem(oauth.openid.server_metadata, "_loaded_at", 0.0)
    request = SimpleNamespace(session={})

    response = await oauth.openid.authorize_redirect(
        request, "https://romm.example.com/api/oauth/openid"
    )

    params = parse_qs(urlparse(response.headers["location"]).query)
    assert params["code_challenge_method"] == ["S256"]

    state_data = await oauth.openid.framework.get_state_data(
        request.session, params["state"][0]
    )
    assert params["code_challenge"] == [_s256(state_data["code_verifier"])]


def _route(router: APIRouter, path: str) -> APIRoute:
    return next(r for r in router.routes if isinstance(r, APIRoute) and r.path == path)


def test_protected_route_documents_the_scope_errors():
    # Arrange
    router = APIRouter()

    @protected_route(router.get, "/scoped", [Scope.ROMS_READ])
    def scoped(request: Request) -> None: ...

    @protected_route(router.get, "/open")
    def open_route(request: Request) -> None: ...

    # Act
    scoped_responses = _route(router, "/scoped").responses
    open_responses = _route(router, "/open").responses

    # Assert
    assert set(scoped_responses) == {401, 403}
    assert open_responses == {}


def test_protected_route_keeps_a_route_specific_description():
    # Arrange
    router = APIRouter()
    own = {403: {"description": "The caller does not own the rom."}}

    @protected_route(router.get, "/owned", [Scope.ROMS_READ], responses=own)
    def owned(request: Request) -> None: ...

    # Act
    description = _route(router, "/owned").responses[403]["description"]

    # Assert
    assert description.startswith("The caller does not own the rom. Also returned")
    assert own[403] == {"description": "The caller does not own the rom."}
