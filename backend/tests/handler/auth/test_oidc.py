from unittest.mock import MagicMock

import pytest
from authlib.integrations.starlette_client.apps import StarletteOAuth2App
from fastapi import HTTPException
from joserfc.jwt import Token

from handler.auth.base_handler import OpenIDHandler
from models.user import Role

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
    mock_user = MagicMock(enabled=True, role=Role.VIEWER)
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


@pytest.mark.parametrize(
    "config_override,token_roles,romm_role",
    [
        # Without OIDC role mapping.
        [{"OIDC_CLAIM_ROLES": ""}, ["admin", "editor"], Role.VIEWER],
        # OIDC role mapping.
        [{}, ["admin", "editor", "viewer"], Role.ADMIN],
        [{}, ["editor", "viewer"], Role.EDITOR],
        [{}, ["viewer"], Role.VIEWER],
        # OIDC viewer role fallback.
        [{"OIDC_ROLE_VIEWER": "*"}, [], Role.VIEWER],
    ],
    ids=["no-mapping", "admin-role", "editor-role", "viewer-role", "viewer-fallback"],
)
async def test_oidc_valid_add_user(
    mocker,
    mock_oidc_enabled,
    mock_token,
    mock_openid_configuration,
    config_override,
    token_roles,
    romm_role,
):
    """Test user creation & role assignment on login."""
    mocker.patch(
        "handler.auth.base_handler.OIDC_CLAIM_ROLES",
        config_override.get("OIDC_CLAIM_ROLES", "roles"),
    )
    mocker.patch(
        "handler.auth.base_handler.OIDC_ROLE_ADMIN",
        config_override.get("OIDC_ROLE_ADMIN", "admin"),
    )
    mocker.patch(
        "handler.auth.base_handler.OIDC_ROLE_EDITOR",
        config_override.get("OIDC_ROLE_EDITOR", "editor"),
    )
    mocker.patch(
        "handler.auth.base_handler.OIDC_ROLE_VIEWER",
        config_override.get("OIDC_ROLE_VIEWER", "viewer"),
    )
    mock_token["userinfo"]["roles"] = token_roles
    mock_user = MagicMock(enabled=True, role=Role.VIEWER)
    mock_add_user = mocker.patch(
        "handler.database.db_user_handler.add_user", return_value=mock_user
    )
    mocker.patch.object(
        StarletteOAuth2App,
        "load_server_metadata",
        return_value=mock_openid_configuration,
    )

    oidc_handler = OpenIDHandler()
    await oidc_handler.get_current_active_user_from_openid_token(mock_token)

    mock_add_user.assert_called_once()
    assert (
        mock_add_user.call_args.args[0].username
        == mock_token["userinfo"]["preferred_username"]
    )
    assert mock_add_user.call_args.args[0].email == mock_token["userinfo"]["email"]
    assert mock_add_user.call_args.args[0].enabled
    assert mock_add_user.call_args.args[0].role == romm_role


async def test_oidc_valid_edit_user_role(
    mocker,
    mock_oidc_enabled,
    mock_token,
    mock_openid_configuration,
):
    """Test role change for existing user on login based on OIDC role mapping."""
    mocker.patch("handler.auth.base_handler.OIDC_CLAIM_ROLES", "roles")
    mocker.patch("handler.auth.base_handler.OIDC_ROLE_ADMIN", "admin")
    mock_token["userinfo"]["roles"] = ["admin"]
    mock_user = MagicMock(enabled=True, role=Role.VIEWER)
    mocker.patch(
        "handler.database.db_user_handler.get_user_by_email", return_value=mock_user
    )
    mock_user_edited = MagicMock(enabled=True, role=Role.ADMIN)
    mock_edit_user = mocker.patch(
        "handler.database.db_user_handler.update_user", return_value=mock_user_edited
    )
    mocker.patch.object(
        StarletteOAuth2App,
        "load_server_metadata",
        return_value=mock_openid_configuration,
    )

    oidc_handler = OpenIDHandler()
    user, _ = await oidc_handler.get_current_active_user_from_openid_token(mock_token)

    assert user == mock_user_edited
    mock_edit_user.assert_called_once_with(mock_user.id, {"role": Role.ADMIN})


async def test_oidc_valid_no_edit_user_role_if_mapping_disabled(
    mocker,
    mock_oidc_enabled,
    mock_token,
    mock_openid_configuration,
):
    """Test that role is not changed for existing user on login if OIDC role mapping is disabled."""
    mock_token["userinfo"]["roles"] = ["admin"]
    mock_user = MagicMock(enabled=True, role=Role.EDITOR)
    mocker.patch(
        "handler.database.db_user_handler.get_user_by_email", return_value=mock_user
    )
    mock_edit_user = mocker.patch(
        "handler.database.db_user_handler.update_user", return_value=mock_user
    )
    mocker.patch.object(
        StarletteOAuth2App,
        "load_server_metadata",
        return_value=mock_openid_configuration,
    )

    oidc_handler = OpenIDHandler()
    user, _ = await oidc_handler.get_current_active_user_from_openid_token(mock_token)

    mock_edit_user.assert_not_called()


async def test_oidc_invalid_user_no_roles(
    mocker,
    mock_oidc_enabled,
    mock_token,
    mock_openid_configuration,
):
    """Test valid token response for user with no roles/access to this application."""
    mocker.patch("handler.auth.base_handler.OIDC_CLAIM_ROLES", "roles")
    mock_token["userinfo"]["roles"] = ["not-mapped"]
    mocker.patch.object(
        StarletteOAuth2App,
        "load_server_metadata",
        return_value=mock_openid_configuration,
    )

    oidc_handler = OpenIDHandler()
    with pytest.raises(HTTPException, match="has not been granted any roles"):
        await oidc_handler.get_current_active_user_from_openid_token(mock_token)


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
    mock_user = MagicMock(enabled=True, role=Role.VIEWER)
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
