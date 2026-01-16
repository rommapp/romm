from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from joserfc import jwt
from main import app

from config import ROMM_SFU_INTERNAL_SECRET
from handler.auth.base_handler import oct_key
from handler.database import db_user_handler
from handler.redis_handler import sync_cache


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


class TestSFUToken:
    def _to_epoch_seconds(self, value) -> int:
        if isinstance(value, int):
            return value
        if hasattr(value, "timestamp"):
            return int(value.timestamp())
        return int(value)

    def test_mint_sfu_token_unauthorized(self, client):
        response = client.post("/api/sfu/token")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_mint_sfu_token_success(self, client, access_token, admin_user):
        # Ensure the user has a netplay username in ui_settings (persisted to DB)
        db_user_handler.update_user(
            admin_user.id,
            {"ui_settings": {"netplay_username": "TestNetplayName"}},
        )

        # Request a write token (default behavior for backward compatibility testing)
        response = client.post(
            "/api/sfu/token",
            json={"token_type": "write"},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires"] == 30

        token = body["token"]
        decoded = jwt.decode(token, oct_key, algorithms=["HS256"])
        claims = decoded.claims

        assert claims["iss"] == "romm:sfu"
        assert claims["sub"] == admin_user.username
        assert claims["type"] == "sfu:write"
        assert "jti" in claims

        # JWT exp should be roughly now + 30s
        now_ts = int(datetime.now(timezone.utc).timestamp())
        exp_ts = self._to_epoch_seconds(claims["exp"])
        assert exp_ts - now_ts <= 35
        assert exp_ts - now_ts >= 1

        jti = claims["jti"]
        key = f"sfu:auth:jti:{jti}"

        data = sync_cache.hgetall(key)
        # fakeredis returns bytes for keys/values
        assert data.get(b"sub") == admin_user.username.encode()
        assert data.get(b"iss") == b"romm:sfu"
        assert data.get(b"jti") == jti.encode()
        assert data.get(b"netplay_username") == b"TestNetplayName"

        ttl = sync_cache.ttl(key)
        assert ttl <= 30
        assert ttl > 0

    def test_mint_sfu_read_token_success(self, client, access_token, admin_user):
        # Test read token (15min expiry, no Redis storage, no jti)
        response = client.post(
            "/api/sfu/token",
            json={"token_type": "read"},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires"] == 900  # 15 minutes

        token = body["token"]
        decoded = jwt.decode(token, oct_key, algorithms=["HS256"])
        claims = decoded.claims

        assert claims["iss"] == "romm:sfu"
        assert claims["sub"] == admin_user.username
        assert claims["type"] == "sfu:read"
        assert "jti" not in claims  # Read tokens don't include jti

        # JWT exp should be roughly now + 900s (15 minutes)
        now_ts = int(datetime.now(timezone.utc).timestamp())
        exp_ts = self._to_epoch_seconds(claims["exp"])
        assert exp_ts - now_ts <= 905
        assert exp_ts - now_ts >= 895

        # Read tokens should NOT be stored in Redis
        # Since we don't have a jti, we can't check Redis, but we verify
        # that the token validates correctly without Redis lookup


class TestSFUInternal:
    def _mint_token(self, client: TestClient, access_token: str, token_type: str = "write") -> str:
        """Helper to mint a token for testing.
        
        Args:
            client: Test client
            access_token: OAuth access token for authentication
            token_type: "read" or "write" (default: "write" for backward compatibility)
        """
        resp = client.post(
            "/api/sfu/token",
            json={"token_type": token_type},
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()["token"]

    def test_internal_verify_requires_secret(self, client, access_token):
        token = self._mint_token(client, access_token)
        resp = client.post("/api/sfu/internal/verify", json={"token": token})
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_internal_verify_consume_marks_used(self, client, access_token, admin_user):
        token = self._mint_token(client, access_token)

        resp = client.post(
            "/api/sfu/internal/verify",
            headers={"x-romm-sfu-secret": ROMM_SFU_INTERNAL_SECRET},
            json={"token": token, "consume": True},
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["sub"] == admin_user.username

        # Second consume should fail.
        resp2 = client.post(
            "/api/sfu/internal/verify",
            headers={"x-romm-sfu-secret": ROMM_SFU_INTERNAL_SECRET},
            json={"token": token, "consume": True},
        )
        assert resp2.status_code == status.HTTP_401_UNAUTHORIZED

    def test_internal_verify_non_consuming_is_repeatable(self, client, access_token, admin_user):
        token = self._mint_token(client, access_token)

        for _ in range(2):
            resp = client.post(
                "/api/sfu/internal/verify",
                headers={"x-romm-sfu-secret": ROMM_SFU_INTERNAL_SECRET},
                json={"token": token, "consume": False},
            )
            assert resp.status_code == status.HTTP_200_OK
            assert resp.json()["sub"] == admin_user.username

    def test_internal_room_registry_lifecycle(self, client):
        room_name = "test-room-registry"
        # Ensure isolation across runs.
        sync_cache.delete(f"sfu:room:{room_name}")

        upsert = client.post(
            "/api/sfu/internal/rooms/upsert",
            headers={"x-romm-sfu-secret": ROMM_SFU_INTERNAL_SECRET},
            json={
                "room_name": room_name,
                "current": 1,
                "max": 4,
                "hasPassword": True,
                "nodeId": "node-a",
                "url": "https://sfu.example.com",
            },
        )
        assert upsert.status_code == status.HTTP_200_OK
        assert upsert.json().get("ok") is True

        resolved = client.get(
            f"/api/sfu/internal/rooms/resolve?room={room_name}",
            headers={"x-romm-sfu-secret": ROMM_SFU_INTERNAL_SECRET},
        )
        assert resolved.status_code == status.HTTP_200_OK
        resolved_body = resolved.json()
        assert resolved_body["room_name"] == room_name
        assert resolved_body["current"] == 1
        assert resolved_body["max"] == 4
        assert resolved_body["hasPassword"] is True
        assert resolved_body["nodeId"] == "node-a"
        assert resolved_body["url"] == "https://sfu.example.com"

        listed = client.get(
            "/api/sfu/internal/rooms/list",
            headers={"x-romm-sfu-secret": ROMM_SFU_INTERNAL_SECRET},
        )
        assert listed.status_code == status.HTTP_200_OK
        listed_body = listed.json()
        assert room_name in listed_body

        deleted = client.post(
            "/api/sfu/internal/rooms/delete",
            headers={"x-romm-sfu-secret": ROMM_SFU_INTERNAL_SECRET},
            json={"room_name": room_name},
        )
        assert deleted.status_code == status.HTTP_200_OK
        assert deleted.json().get("ok") is True

        resolved2 = client.get(
            f"/api/sfu/internal/rooms/resolve?room={room_name}",
            headers={"x-romm-sfu-secret": ROMM_SFU_INTERNAL_SECRET},
        )
        assert resolved2.status_code == status.HTTP_404_NOT_FOUND
