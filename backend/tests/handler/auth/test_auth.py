from base64 import b64encode

import pytest
from fastapi import status
from fastapi.exceptions import HTTPException
from starlette.requests import HTTPConnection

from handler.auth import auth_handler, oauth_handler
from handler.auth.constants import EDIT_SCOPES
from handler.auth.hybrid_auth import HybridAuthBackend
from handler.database import db_user_handler
from models.user import User


def test_verify_password():
    assert auth_handler.verify_password(
        "password", auth_handler.get_password_hash("password")
    )
    assert not auth_handler.verify_password(
        "password", auth_handler.get_password_hash("notpassword")
    )


def test_authenticate_user(admin_user: User):
    current_user = auth_handler.authenticate_user("test_admin", "test_admin_password")

    assert current_user
    assert current_user.id == admin_user.id


async def test_get_current_active_user_from_session(editor_user: User):
    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self.scope["session"] = {"iss": "romm:auth", "sub": editor_user.username}

    conn = MockConnection()
    current_user = await auth_handler.get_current_active_user_from_session(conn)

    assert current_user
    assert isinstance(current_user, User)
    assert current_user.id == editor_user.id


async def test_get_current_active_user_from_session_bad_username(editor_user: User):
    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self.scope["session"] = {"iss": "romm:auth", "sub": "not_real_username"}

    conn = MockConnection()

    try:
        await auth_handler.get_current_active_user_from_session(conn)
    except HTTPException as e:
        assert e.status_code == status.HTTP_403_FORBIDDEN
        assert e.detail == "User not found"


async def test_get_current_active_user_from_session_disabled_user(editor_user: User):
    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self.scope["session"] = {"iss": "romm:auth", "sub": editor_user.username}
            self._headers = {}

    conn = MockConnection()

    db_user_handler.update_user(editor_user.id, {"enabled": False})

    try:
        await auth_handler.get_current_active_user_from_session(conn)
    except HTTPException as e:
        assert e.status_code == status.HTTP_403_FORBIDDEN
        assert e.detail == "Inactive user test_editor"


async def test_hybrid_auth_backend_session(editor_user: User):
    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self.scope["session"] = {"iss": "romm:auth", "sub": editor_user.username}

    backend = HybridAuthBackend()
    conn = MockConnection()

    result = await backend.authenticate(conn)
    assert result is not None

    creds, user = result
    assert user.id == editor_user.id
    assert creds.scopes == editor_user.oauth_scopes
    assert creds.scopes == EDIT_SCOPES


async def test_hybrid_auth_backend_empty_session_and_headers(editor_user: User):
    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self._headers = {}

    backend = HybridAuthBackend()
    conn = MockConnection()

    result = await backend.authenticate(conn)
    assert result is None


async def test_hybrid_auth_backend_bearer_auth_header(editor_user: User):
    access_token = oauth_handler.create_oauth_token(
        data={
            "sub": editor_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(editor_user.oauth_scopes),
            "type": "access",
        },
    )

    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self._headers = {"Authorization": f"Bearer {access_token}"}

    backend = HybridAuthBackend()
    conn = MockConnection()

    result = await backend.authenticate(conn)
    assert result is not None

    creds, user = result
    assert user.id == editor_user.id
    assert set(creds.scopes).issubset(editor_user.oauth_scopes)


async def test_hybrid_auth_backend_bearer_invalid_token(editor_user: User):
    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self._headers = {"Authorization": "Bearer invalid_token"}

    backend = HybridAuthBackend()
    conn = MockConnection()

    with pytest.raises(HTTPException):
        await backend.authenticate(conn)


async def test_hybrid_auth_backend_basic_auth_header(editor_user: User):
    token = b64encode(b"test_editor:test_editor_password").decode()

    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self._headers = {"Authorization": f"Basic {token}"}

    backend = HybridAuthBackend()
    conn = MockConnection()

    result = await backend.authenticate(conn)
    assert result is not None

    creds, user = result
    assert user.id == editor_user.id
    assert creds.scopes == EDIT_SCOPES
    assert set(creds.scopes).issubset(editor_user.oauth_scopes)


async def test_hybrid_auth_backend_basic_auth_header_unencoded(editor_user: User):
    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self._headers = {"Authorization": "Basic test_editor:test_editor_password"}

    backend = HybridAuthBackend()
    conn = MockConnection()

    with pytest.raises(HTTPException):
        await backend.authenticate(conn)


async def test_hybrid_auth_backend_invalid_scheme():
    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self._headers = {"Authorization": "Some invalid_scheme"}

    backend = HybridAuthBackend()
    conn = MockConnection()

    result = await backend.authenticate(conn)
    assert result is None


async def test_hybrid_auth_backend_with_refresh_token(editor_user: User):
    refresh_token = oauth_handler.create_oauth_token(
        data={
            "sub": editor_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(editor_user.oauth_scopes),
            "type": "refresh",
        },
    )

    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self._headers = {"Authorization": f"Bearer {refresh_token}"}

    backend = HybridAuthBackend()
    conn = MockConnection()

    result = await backend.authenticate(conn)
    assert result is None


async def test_hybrid_auth_backend_scope_subset(editor_user: User):
    scopes = editor_user.oauth_scopes[:3]
    access_token = oauth_handler.create_oauth_token(
        data={
            "sub": editor_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(scopes),
            "type": "access",
        },
    )

    class MockConnection(HTTPConnection):
        def __init__(self):
            self.scope: dict[str, dict] = {"session": {}}
            self._headers = {"Authorization": f"Bearer {access_token}"}

    backend = HybridAuthBackend()
    conn = MockConnection()

    result = await backend.authenticate(conn)
    assert result is not None

    creds, user = result
    assert user.id == editor_user.id
    assert set(creds.scopes).issubset(editor_user.oauth_scopes)
    assert set(creds.scopes).issubset(scopes)
