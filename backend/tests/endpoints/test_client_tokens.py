from datetime import timedelta

import pytest
from fastapi import status

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth import auth_handler, oauth_handler
from handler.database import db_client_token_handler, db_user_handler
from handler.redis_handler import sync_cache
from models.client_token import ClientToken
from models.user import Role


@pytest.fixture
def viewer_access_token(viewer_user):
    return oauth_handler.create_access_token(
        data={
            "sub": viewer_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(viewer_user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )


class TestClientTokenCRUD:
    def test_create_token(self, client, access_token, admin_user):
        response = client.post(
            "/api/client-tokens",
            json={
                "name": "My Device",
                "scopes": ["roms.read", "assets.read"],
                "expires_in": "90d",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["name"] == "My Device"
        assert body["raw_token"].startswith("rmm_")
        assert len(body["raw_token"]) == 68
        assert set(body["scopes"]) == {"roms.read", "assets.read"}
        assert body["expires_at"] is not None
        assert body["user_id"] == admin_user.id

    def test_create_token_minimal(self, client, access_token, admin_user):
        response = client.post(
            "/api/client-tokens",
            json={
                "name": "Never Expires",
                "scopes": ["roms.read"],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["expires_at"] is None
        assert body["raw_token"].startswith("rmm_")

    def test_list_tokens(self, client, access_token, admin_user):
        for name in ["Token A", "Token B"]:
            client.post(
                "/api/client-tokens",
                json={"name": name, "scopes": ["roms.read"]},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        response = client.get(
            "/api/client-tokens",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()
        assert len(tokens) == 2
        names = {t["name"] for t in tokens}
        assert names == {"Token A", "Token B"}
        for t in tokens:
            assert "raw_token" not in t

    def test_delete_token(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "To Delete", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/client-tokens/{token_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK

        list_resp = client.get(
            "/api/client-tokens",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert len(list_resp.json()) == 0

    def test_delete_token_not_found(self, client, access_token, admin_user):
        response = client.delete(
            "/api/client-tokens/99999",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_regenerate_token(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={
                "name": "Regenerable",
                "scopes": ["roms.read"],
                "expires_in": "30d",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        old_raw = create_resp.json()["raw_token"]
        token_id = create_resp.json()["id"]

        regen_resp = client.put(
            f"/api/client-tokens/{token_id}/regenerate",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert regen_resp.status_code == status.HTTP_200_OK
        body = regen_resp.json()
        new_raw = body["raw_token"]
        assert new_raw.startswith("rmm_")
        assert new_raw != old_raw
        assert body["name"] == "Regenerable"
        assert body["scopes"] == ["roms.read"]
        assert body["expires_at"] is not None

        # Old token should no longer work
        old_hash = auth_handler.hash_client_token(old_raw)
        assert db_client_token_handler.get_token_by_hash(old_hash) is None

        # New token should work
        new_hash = auth_handler.hash_client_token(new_raw)
        assert db_client_token_handler.get_token_by_hash(new_hash) is not None

    def test_create_token_limit(self, client, access_token, admin_user):
        for i in range(25):
            resp = client.post(
                "/api/client-tokens",
                json={"name": f"Token {i}", "scopes": ["roms.read"]},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert resp.status_code == status.HTTP_201_CREATED

        resp = client.post(
            "/api/client-tokens",
            json={"name": "Token 26", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_token_invalid_expiry(self, client, access_token, admin_user):
        response = client.post(
            "/api/client-tokens",
            json={
                "name": "Bad Expiry",
                "scopes": ["roms.read"],
                "expires_in": "999x",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestClientTokenAuth:
    def test_authenticate_with_client_token(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Auth Test", "scopes": ["roms.read", "platforms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raw_token = create_resp.json()["raw_token"]

        # Use the client token to hit a protected endpoint
        response = client.get(
            "/api/platforms",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_expired_token_rejected(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={
                "name": "Expired",
                "scopes": ["roms.read", "platforms.read"],
                "expires_in": "30d",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raw_token = create_resp.json()["raw_token"]
        token_id = create_resp.json()["id"]

        # Manually set expires_at to the past
        from tests.conftest import session

        with session.begin() as s:
            from datetime import datetime, timezone

            s.query(ClientToken).filter_by(id=token_id).update(
                {"expires_at": datetime(2020, 1, 1, tzinfo=timezone.utc)}
            )

        response = client.get(
            "/api/platforms",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_revoked_token_rejected(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Revoked", "scopes": ["roms.read", "platforms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raw_token = create_resp.json()["raw_token"]
        token_id = create_resp.json()["id"]

        client.delete(
            f"/api/client-tokens/{token_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        response = client.get(
            "/api/platforms",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_scope_enforcement(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Read Only", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raw_token = create_resp.json()["raw_token"]

        # roms.read should allow listing platforms? No -- need platforms.read
        response = client.get(
            "/api/platforms",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_scope_intersection_on_demotion(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={
                "name": "Admin Token",
                "scopes": ["users.write", "roms.read", "platforms.read"],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raw_token = create_resp.json()["raw_token"]

        # Demote user to viewer
        db_user_handler.update_user(admin_user.id, {"role": Role.VIEWER})

        # users.write should no longer be effective
        response = client.get(
            "/api/users",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Restore admin role for other tests
        db_user_handler.update_user(admin_user.id, {"role": Role.ADMIN})

    def test_disabled_user_rejected(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Disabled", "scopes": ["roms.read", "platforms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        raw_token = create_resp.json()["raw_token"]

        db_user_handler.update_user(admin_user.id, {"enabled": False})

        response = client.get(
            "/api/platforms",
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Re-enable for other tests
        db_user_handler.update_user(admin_user.id, {"enabled": True})

    def test_invalid_token_format(self, client, admin_user):
        response = client.get(
            "/api/platforms",
            headers={"Authorization": "Bearer rmm_invalidgarbage"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_scopes_subset_validation(self, client, viewer_access_token, viewer_user):
        response = client.post(
            "/api/client-tokens",
            json={
                "name": "Overreach",
                "scopes": ["users.write"],
            },
            headers={"Authorization": f"Bearer {viewer_access_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestClientTokenUserIsolation:
    def test_list_only_own_tokens(
        self,
        client,
        access_token,
        editor_access_token,
        admin_user,
        editor_user,
    ):
        client.post(
            "/api/client-tokens",
            json={"name": "Admin Token", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        client.post(
            "/api/client-tokens",
            json={"name": "Editor Token", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

        admin_list = client.get(
            "/api/client-tokens",
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        editor_list = client.get(
            "/api/client-tokens",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        ).json()

        assert len(admin_list) == 1
        assert admin_list[0]["name"] == "Admin Token"
        assert len(editor_list) == 1
        assert editor_list[0]["name"] == "Editor Token"

    def test_cannot_delete_other_users_token(
        self,
        client,
        access_token,
        editor_access_token,
        admin_user,
        editor_user,
    ):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Editor's Token", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        token_id = create_resp.json()["id"]

        # Admin tries to delete via user endpoint (not admin endpoint)
        response = client.delete(
            f"/api/client-tokens/{token_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Verify token still exists
        editor_tokens = client.get(
            "/api/client-tokens",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        ).json()
        assert len(editor_tokens) == 1

    def test_cannot_regenerate_other_users_token(
        self,
        client,
        access_token,
        editor_access_token,
        admin_user,
        editor_user,
    ):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Editor's Token", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        token_id = create_resp.json()["id"]

        response = client.put(
            f"/api/client-tokens/{token_id}/regenerate",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_admin_can_list_all_tokens(
        self,
        client,
        access_token,
        editor_access_token,
        admin_user,
        editor_user,
    ):
        client.post(
            "/api/client-tokens",
            json={"name": "Admin Token", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        client.post(
            "/api/client-tokens",
            json={"name": "Editor Token", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

        response = client.get(
            "/api/client-tokens/all",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()
        assert len(tokens) == 2
        usernames = {t["username"] for t in tokens}
        assert usernames == {"test_admin", "test_editor"}


class TestClientTokenPairing:
    def test_pair_creates_code(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Pair Test", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_id = create_resp.json()["id"]

        response = client.post(
            f"/api/client-tokens/{token_id}/pair",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert len(body["code"]) == 8
        assert body["expires_in"] == 60

    def test_exchange_returns_token(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Exchange Test", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_id = create_resp.json()["id"]
        old_raw = create_resp.json()["raw_token"]

        pair_resp = client.post(
            f"/api/client-tokens/{token_id}/pair",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        code = pair_resp.json()["code"]

        exchange_resp = client.post(
            "/api/client-tokens/exchange",
            json={"code": code},
        )
        assert exchange_resp.status_code == status.HTTP_200_OK
        new_raw = exchange_resp.json()["raw_token"]
        assert new_raw.startswith("rmm_")
        assert new_raw != old_raw

        # Old credential should be dead
        old_hash = auth_handler.hash_client_token(old_raw)
        assert db_client_token_handler.get_token_by_hash(old_hash) is None

        # New credential should work
        new_hash = auth_handler.hash_client_token(new_raw)
        assert db_client_token_handler.get_token_by_hash(new_hash) is not None

    def test_exchange_expired_code(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Expired Code", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_id = create_resp.json()["id"]

        pair_resp = client.post(
            f"/api/client-tokens/{token_id}/pair",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        code = pair_resp.json()["code"]

        # Delete the Redis key to simulate expiry
        sync_cache.delete(f"pair:{code}")

        exchange_resp = client.post(
            "/api/client-tokens/exchange",
            json={"code": code},
        )
        assert exchange_resp.status_code == status.HTTP_404_NOT_FOUND

    def test_exchange_replay_rejected(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Replay Test", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_id = create_resp.json()["id"]

        pair_resp = client.post(
            f"/api/client-tokens/{token_id}/pair",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        code = pair_resp.json()["code"]

        # First exchange succeeds
        resp1 = client.post(
            "/api/client-tokens/exchange",
            json={"code": code},
        )
        assert resp1.status_code == status.HTTP_200_OK

        # Second exchange with same code fails
        resp2 = client.post(
            "/api/client-tokens/exchange",
            json={"code": code},
        )
        assert resp2.status_code == status.HTTP_404_NOT_FOUND

    def test_exchange_invalid_code(self, client):
        response = client.post(
            "/api/client-tokens/exchange",
            json={"code": "ZZZZZZZZ"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_exchange_case_insensitive(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Case Test", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_id = create_resp.json()["id"]

        pair_resp = client.post(
            f"/api/client-tokens/{token_id}/pair",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        code = pair_resp.json()["code"]

        exchange_resp = client.post(
            "/api/client-tokens/exchange",
            json={"code": code.lower()},
        )
        assert exchange_resp.status_code == status.HTTP_200_OK

    def test_pair_status_pending(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Status Test", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_id = create_resp.json()["id"]

        pair_resp = client.post(
            f"/api/client-tokens/{token_id}/pair",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        code = pair_resp.json()["code"]

        status_resp = client.get(f"/api/client-tokens/pair/{code}/status")
        assert status_resp.status_code == status.HTTP_200_OK

    def test_pair_status_after_exchange(self, client, access_token, admin_user):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Status After", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_id = create_resp.json()["id"]

        pair_resp = client.post(
            f"/api/client-tokens/{token_id}/pair",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        code = pair_resp.json()["code"]

        client.post(
            "/api/client-tokens/exchange",
            json={"code": code},
        )

        status_resp = client.get(f"/api/client-tokens/pair/{code}/status")
        assert status_resp.status_code == status.HTTP_404_NOT_FOUND

    def test_exchange_rate_limit(self, client):
        for _ in range(5):
            client.post(
                "/api/client-tokens/exchange",
                json={"code": "BADCODE1"},
            )

        response = client.post(
            "/api/client-tokens/exchange",
            json={"code": "BADCODE2"},
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestClientTokenAdmin:
    def test_admin_list_all(
        self,
        client,
        access_token,
        editor_access_token,
        admin_user,
        editor_user,
    ):
        client.post(
            "/api/client-tokens",
            json={"name": "Admin's", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        client.post(
            "/api/client-tokens",
            json={"name": "Editor's", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

        response = client.get(
            "/api/client-tokens/all",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        tokens = response.json()
        assert len(tokens) == 2
        for t in tokens:
            assert "username" in t

    def test_admin_revoke_other_user_token(
        self,
        client,
        access_token,
        editor_access_token,
        admin_user,
        editor_user,
    ):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Editor Token", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        token_id = create_resp.json()["id"]
        raw_token = create_resp.json()["raw_token"]

        response = client.delete(
            f"/api/client-tokens/{token_id}/admin",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK

        # Verify token no longer authenticates
        hashed = auth_handler.hash_client_token(raw_token)
        assert db_client_token_handler.get_token_by_hash(hashed) is None

    def test_non_admin_cannot_list_all(self, client, editor_access_token, editor_user):
        response = client.get(
            "/api/client-tokens/all",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_admin_cannot_admin_revoke(
        self,
        client,
        access_token,
        editor_access_token,
        admin_user,
        editor_user,
    ):
        create_resp = client.post(
            "/api/client-tokens",
            json={"name": "Admin's Token", "scopes": ["roms.read"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        token_id = create_resp.json()["id"]

        response = client.delete(
            f"/api/client-tokens/{token_id}/admin",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
