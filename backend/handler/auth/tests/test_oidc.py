from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from handler.auth.base_handler import OpenIDHandler
from joserfc.jwt import Token

# Mock constants
OIDC_SERVER_APPLICATION_URL = "http://mock-oidc-server"
OIDC_ENABLED = True


@pytest.fixture
def mock_oidc_disabled(mocker):
    mocker.patch("handler.auth.base_handler.OIDC_ENABLED", False)


@pytest.fixture
def mock_oidc_enabled(mocker):
    mocker.patch("handler.auth.base_handler.OIDC_ENABLED", True)


@pytest.fixture
def mock_token():
    return {
        "access_token": "",
        "token_type": "Bearer",
        "expires_in": 300,
        "id_token": "",
        "expires_at": 1735397872,
        "userinfo": {
            "iss": "http://localhost:9000/application/o/romm/",
            "sub": "",
            "aud": "",
            "exp": 1735397871,
            "iat": 1735397571,
            "auth_time": 1735397571,
            "acr": "goauthentik.io/providers/oauth2/default",
            "amr": ["pwd"],
            "nonce": "",
            "sid": "",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "given_name": "Test User",
            "preferred_username": "testuser",
            "nickname": "testuser",
            "groups": ["Default Users"],
        },
    }


async def test_oidc_disabled(mock_oidc_disabled, mock_token):
    """Test that OIDC is disabled."""
    oidc_handler = OpenIDHandler()
    user, userinfo = await oidc_handler.get_current_active_user_from_openid_token(
        mock_token
    )
    assert user is None
    assert userinfo is None


async def test_oidc_valid_token_decoding(mocker, mock_oidc_enabled, mock_token):
    """Test token decoding with valid RSA key and token."""
    mock_jwt_payload = Token(
        header={"alg": "RS256"},
        claims={"iss": OIDC_SERVER_APPLICATION_URL, "email": "test@example.com"},
    )
    mock_user = MagicMock(enabled=True)
    mocker.patch(
        "handler.database.db_user_handler.get_user_by_email", return_value=mock_user
    )

    oidc_handler = OpenIDHandler()
    user, userinfo = await oidc_handler.get_current_active_user_from_openid_token(
        mock_token
    )

    assert user is not None
    assert userinfo is not None

    assert user == mock_user
    assert userinfo.get("email") == mock_jwt_payload.claims.get("email")


async def test_oidc_invalid_token_signature(mock_oidc_enabled):
    """Test token decoding raises exception for invalid signature."""
    oidc_handler = OpenIDHandler()
    token = {"id_token": "invalid_signature_token"}
    with pytest.raises(HTTPException):
        await oidc_handler.get_current_active_user_from_openid_token(token)
