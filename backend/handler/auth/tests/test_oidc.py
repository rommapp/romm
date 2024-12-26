from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from handler.auth.base_handler import OpenIDHandler, ctx_httpx_client
from httpx import Request, RequestError, Response
from joserfc.errors import BadSignatureError
from joserfc.jwt import Token

# Mock constants
OIDC_SERVER_APPLICATION_URL = "http://mock-oidc-server"
OIDC_ENABLED = True


@pytest.fixture
def mock_oidc_disabled(mocker):
    mocker.patch("handler.auth.base_handler.OIDC_ENABLED", False)


@pytest.fixture
def mock_oidc_enabled(mocker):
    mocker.patch(
        "handler.auth.base_handler.OIDC_SERVER_APPLICATION_URL",
        OIDC_SERVER_APPLICATION_URL,
    )
    mocker.patch("handler.auth.base_handler.OIDC_ENABLED", True)


@pytest.fixture
def mock_httpx_client():
    """Fixture to mock the httpx.AsyncClient and set it in the ContextVar."""
    mock_client = AsyncMock()
    token = ctx_httpx_client.set(mock_client)
    yield mock_client
    ctx_httpx_client.reset(token)


@pytest.fixture
def mock_request():
    return Request("GET", f"{OIDC_SERVER_APPLICATION_URL}/jwks/")


def test_oidc_disabled_initialization(mock_oidc_disabled):
    """Test that the handler initializes correctly when OIDC is disabled."""
    oidc_handler = OpenIDHandler()
    assert oidc_handler._rsa_key is None


async def test_oidc_enabled_server_unreachable(
    mock_httpx_client, mock_request, mock_oidc_enabled
):
    """Test that initialization raises an HTTPException when the OIDC server is unreachable."""
    mock_httpx_client.get.side_effect = RequestError(
        "Mocked error", request=mock_request
    )

    oidc_handler = OpenIDHandler()
    token = {"id_token": "invalid_signature_token"}
    with pytest.raises(HTTPException):
        await oidc_handler.get_current_active_user_from_openid_token(token)


async def test_oidc_valid_token_decoding(
    mocker, mock_httpx_client, mock_request, mock_oidc_enabled
):
    """Test token decoding with valid RSA key and token."""
    mock_httpx_client.get.return_value = Response(
        200,
        request=mock_request,
        json={"keys": [{"kty": "RSA", "n": "fake", "e": "AQAB"}]},
    )
    mock_rsa_key = MagicMock()
    mocker.patch(
        "handler.auth.base_handler.RSAKey.import_key", return_value=mock_rsa_key
    )
    mock_jwt_payload = Token(
        header={"alg": "RS256"},
        claims={"iss": OIDC_SERVER_APPLICATION_URL, "email": "test@example.com"},
    )
    mocker.patch("joserfc.jwt.decode", return_value=mock_jwt_payload)
    mock_user = MagicMock(enabled=True)
    mocker.patch(
        "handler.database.db_user_handler.get_user_by_email", return_value=mock_user
    )

    oidc_handler = OpenIDHandler()
    token = {"id_token": "valid_token"}
    user, claims = await oidc_handler.get_current_active_user_from_openid_token(token)

    assert user == mock_user
    assert claims == mock_jwt_payload.claims


async def test_oidc_invalid_token_signature(
    mocker, mock_httpx_client, mock_request, mock_oidc_enabled
):
    """Test token decoding raises exception for invalid signature."""
    mock_httpx_client.get.return_value = Response(
        200,
        request=mock_request,
        json={"keys": [{"kty": "RSA", "n": "fake", "e": "AQAB"}]},
    )
    mock_rsa_key = MagicMock()
    mocker.patch(
        "handler.auth.base_handler.RSAKey.import_key", return_value=mock_rsa_key
    )
    mocker.patch("joserfc.jwt.decode", side_effect=BadSignatureError)

    oidc_handler = OpenIDHandler()
    token = {"id_token": "invalid_signature_token"}
    with pytest.raises(HTTPException):
        await oidc_handler.get_current_active_user_from_openid_token(token)
