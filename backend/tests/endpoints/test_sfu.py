from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from joserfc import jwt
from main import app

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

        response = client.post(
            "/api/sfu/token", headers={"Authorization": f"Bearer {access_token}"}
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
        assert claims["type"] == "sfu"
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
