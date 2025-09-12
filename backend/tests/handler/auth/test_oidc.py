from unittest.mock import MagicMock

import pytest
from authlib.integrations.starlette_client.apps import StarletteOAuth2App
from fastapi import HTTPException
from joserfc.jwt import Token

from handler.auth.base_handler import OpenIDHandler

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


@pytest.fixture
def mock_openid_configuration():
    return {
        "issuer": "https://authentik.example.com/application/o/romm/",
        "authorization_endpoint": "https://authentik.example.com/application/o/authorize/",
        "token_endpoint": "https://authentik.example.com/application/o/token/",
        "userinfo_endpoint": "https://authentik.example.com/application/o/userinfo/",
        "end_session_endpoint": "https://authentik.example.com/application/o/romm/end-session/",
        "introspection_endpoint": "https://authentik.example.com/application/o/introspect/",
        "revocation_endpoint": "https://authentik.example.com/application/o/revoke/",
        "device_authorization_endpoint": "https://authentik.example.com/application/o/device/",
        "response_types_supported": [
            "code",
            "id_token",
            "id_token token",
            "code token",
            "code id_token",
            "code id_token token",
        ],
        "response_modes_supported": ["query", "fragment", "form_post"],
        "jwks_uri": "https://authentik.example.com/application/o/romm/jwks/",
        "grant_types_supported": [
            "authorization_code",
            "refresh_token",
            "implicit",
            "client_credentials",
            "password",
            "urn:ietf:params:oauth:grant-type:device_code",
        ],
        "id_token_signing_alg_values_supported": ["RS256"],
        "subject_types_supported": ["public"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_post",
            "client_secret_basic",
        ],
        "acr_values_supported": ["goauthentik.io/providers/oauth2/default"],
        "scopes_supported": ["openid", "email", "profile"],
        "request_parameter_supported": False,
        "claims_supported": [
            "sub",
            "iss",
            "aud",
            "exp",
            "iat",
            "auth_time",
            "acr",
            "amr",
            "nonce",
            "email",
            "email_verified",
            "name",
            "given_name",
            "preferred_username",
            "nickname",
            "groups",
        ],
        "claims_parameter_supported": False,
        "code_challenge_methods_supported": ["plain", "S256"],
    }


async def test_oidc_disabled(mock_oidc_disabled, mock_token):
    """Test that OIDC is disabled."""
    oidc_handler = OpenIDHandler()
    user, userinfo = await oidc_handler.get_current_active_user_from_openid_token(
        mock_token
    )
    assert user is None
    assert userinfo is None


async def test_oidc_valid_token_decoding(
    mocker, mock_oidc_enabled, mock_token, mock_openid_configuration
):
    """Test token decoding with valid RSA key and token."""
    mock_jwt_payload = Token(
        header={"alg": "RS256"},
        claims={"iss": OIDC_SERVER_APPLICATION_URL, "email": "test@example.com"},
    )
    mock_user = MagicMock(enabled=True)
    mocker.patch(
        "handler.database.db_user_handler.get_user_by_email", return_value=mock_user
    )
    mocker.patch.object(
        StarletteOAuth2App,
        "load_server_metadata",
        return_value=mock_openid_configuration,
    )

    oidc_handler = OpenIDHandler()
    user, userinfo = await oidc_handler.get_current_active_user_from_openid_token(
        mock_token
    )

    assert user is not None
    assert userinfo is not None

    assert user == mock_user
    assert userinfo.get("email") == mock_jwt_payload.claims.get("email")


async def test_oidc_token_unverified_email(
    mocker, mock_oidc_enabled, mock_token, mock_openid_configuration
):
    """Test token decoding for unverified email."""
    mocker.patch.object(
        StarletteOAuth2App,
        "load_server_metadata",
        return_value=mock_openid_configuration,
    )

    unverified_token = mock_token
    unverified_token["userinfo"]["email_verified"] = False

    oidc_handler = OpenIDHandler()
    with pytest.raises(HTTPException):
        await oidc_handler.get_current_active_user_from_openid_token(unverified_token)


async def test_oidc_token_without_email_verified_claim(
    mocker, mock_oidc_enabled, mock_token, mock_openid_configuration
):
    """Test token decoding with server not supporting email_verified claim."""
    mock_jwt_payload = Token(
        header={"alg": "RS256"},
        claims={"iss": OIDC_SERVER_APPLICATION_URL, "email": "test@example.com"},
    )
    mock_user = MagicMock(enabled=True)
    mocker.patch(
        "handler.database.db_user_handler.get_user_by_email", return_value=mock_user
    )

    openid_conf = mock_openid_configuration
    openid_conf["claims_supported"] = openid_conf["claims_supported"].remove(
        "email_verified"
    )
    mocker.patch.object(
        StarletteOAuth2App, "load_server_metadata", return_value=openid_conf
    )

    unverified_token = mock_token
    del unverified_token["userinfo"]["email_verified"]

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
