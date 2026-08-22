from urllib.parse import parse_qs, urlparse

from authlib.integrations.httpx_client import AsyncOAuth2Client

from decorators.auth import oauth


def test_oidc_client_is_configured_for_pkce():
    """The OIDC client must ask Authlib for PKCE.

    Authlib only derives a code_verifier when code_challenge_method is set on
    the client, so this kwarg is what makes the whole flow PKCE-capable.
    """
    assert oauth.openid.client_kwargs["code_challenge_method"] == "S256"


def test_authorization_url_carries_a_code_challenge():
    """The configured method must actually yield PKCE parameters.

    Guards the end of the chain: providers that mandate PKCE reject an
    authorization request with no code_challenge, so asserting the kwarg
    alone would not prove the request is well-formed.
    """
    client = AsyncOAuth2Client(
        client_id="romm",
        code_challenge_method=oauth.openid.client_kwargs["code_challenge_method"],
    )

    url, _state = client.create_authorization_url(
        "https://idp.example.com/authorize", code_verifier="a" * 48
    )

    params = parse_qs(urlparse(url).query)
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"]
