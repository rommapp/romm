import hashlib
from base64 import urlsafe_b64encode
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from decorators.auth import oauth


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
