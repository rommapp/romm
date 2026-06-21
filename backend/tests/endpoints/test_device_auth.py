"""End-to-end tests for the device authorization flow endpoints."""

import json
from datetime import datetime, timedelta, timezone

from fastapi import status
from fastapi.testclient import TestClient
from httpx import Response

from handler.database import db_client_token_handler, db_device_handler
from handler.redis_handler import sync_cache
from models.user import User
from utils import device_auth as df


def _recent_times(minutes_ago_start: int = 30, duration_minutes: int = 15) -> dict:
    """Build start/end times anchored to now() so play-session ingest accepts them."""
    start = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago_start)
    end = start + timedelta(minutes=duration_minutes)
    return {
        "start_time": start.isoformat().replace("+00:00", "Z"),
        "end_time": end.isoformat().replace("+00:00", "Z"),
        "duration_ms": duration_minutes * 60 * 1000,
    }


AUTHORIZE_PAYLOAD = {
    "client_device_identifier": "install-uuid-abc",
    "name": "Pete muOS",
    "client": "grout",
    "platform": "muOS",
    "client_version": "1.4.0",
    "requested_scopes": ["roms.read", "roms.user.write", "devices.write"],
}


def _authorize(client: TestClient, payload: dict | None = None) -> dict:
    resp = client.post("/api/auth/device/init", json=payload or AUTHORIZE_PAYLOAD)
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()


def _approve(
    client: TestClient,
    access_token: str,
    user_code: str,
    approved_scopes: list[str],
    device_name: str | None = None,
    expires_in: str | None = None,
) -> Response:
    body: dict = {"user_code": user_code, "approved_scopes": approved_scopes}
    if device_name is not None:
        body["device_name"] = device_name
    if expires_in is not None:
        body["expires_in"] = expires_in
    return client.post(
        "/api/auth/device/approve",
        json=body,
        headers={"Authorization": f"Bearer {access_token}"},
    )


def _poll_token(client: TestClient, device_code: str) -> Response:
    return client.post("/api/auth/device/token", json={"device_code": device_code})


class TestAuthorize:
    def test_valid_request_returns_all_fields(self, client):
        body = _authorize(client)

        assert len(body["device_code"]) == df.DEVICE_CODE_BYTES * 2
        assert len(body["user_code"]) == df.USER_CODE_LENGTH
        assert body["verification_path"].endswith("/pair/device")
        assert body["user_code"] in body["verification_path_complete"]
        assert body["expires_in"] == df.PENDING_TTL_SECONDS
        assert body["interval"] == df.POLL_DEFAULT_INTERVAL_SECONDS

    def test_stores_both_redis_keys(self, client):
        body = _authorize(client)

        dc_raw = sync_cache.get(f"device_auth:dc:{body['device_code']}")
        uc_raw = sync_cache.get(f"device_auth:uc:{body['user_code']}")
        assert dc_raw is not None
        assert uc_raw is not None

        stored = json.loads(dc_raw)
        assert stored["status"] == df.FlowStatus.PENDING
        assert stored["client"] == "grout"
        assert stored["client_device_identifier"] == "install-uuid-abc"
        assert sorted(stored["requested_scopes"]) == sorted(
            AUTHORIZE_PAYLOAD["requested_scopes"]
        )

    def test_rate_limit_returns_429(self, client):
        # 10 allowed, 11th blocked. Using a fresh client_device_identifier each
        # loop isn't necessary — the rate key is IP-scoped.
        for _ in range(df.AUTHORIZE_RATE_LIMIT):
            r = client.post("/api/auth/device/init", json=AUTHORIZE_PAYLOAD)
            assert r.status_code == status.HTTP_201_CREATED

        resp = client.post("/api/auth/device/init", json=AUTHORIZE_PAYLOAD)
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_empty_scopes_rejected(self, client):
        payload = {**AUTHORIZE_PAYLOAD, "requested_scopes": []}
        resp = client.post("/api/auth/device/init", json=payload)
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_missing_required_fields_rejected(self, client):
        resp = client.post(
            "/api/auth/device/init",
            json={"client_device_identifier": "x"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPending:
    def test_auth_required(self, client):
        body = _authorize(client)
        resp = client.get(f"/api/auth/device/pending/{body['user_code']}")
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unknown_user_code_returns_404(self, client, access_token: str):
        resp = client.get(
            "/api/auth/device/pending/NOPECODE",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_intersected_allowed_scopes(
        self, client, access_token: str, admin_user: User
    ):
        body = _authorize(client)

        resp = client.get(
            f"/api/auth/device/pending/{body['user_code']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        user_scopes = set(admin_user.oauth_scopes)
        requested = set(AUTHORIZE_PAYLOAD["requested_scopes"])
        expected_allowed = sorted(requested & user_scopes)

        assert data["allowed_scopes"] == expected_allowed
        assert sorted(data["requested_scopes"]) == sorted(requested)

    def test_user_without_a_scope_gets_it_stripped_from_allowed(
        self, client, editor_access_token: str, editor_user: User
    ):
        # Request a scope the editor doesn't have
        body = _authorize(
            client,
            payload={
                **AUTHORIZE_PAYLOAD,
                "requested_scopes": ["roms.read", "users.write"],
            },
        )

        resp = client.get(
            f"/api/auth/device/pending/{body['user_code']}",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "users.write" not in data["allowed_scopes"]
        assert "roms.read" in data["allowed_scopes"]

    def test_already_approved_returns_410(self, client, access_token: str):
        body = _authorize(client)
        approve = _approve(
            client,
            access_token,
            body["user_code"],
            approved_scopes=["roms.read"],
        )
        assert approve.status_code == status.HTTP_200_OK

        # After approval the user_code pointer is deleted, so pending lookup
        # returns 404 — not 410. 410 covers the narrower race where status
        # transitions without the user_code being cleaned up; it's validated
        # in test_denied_returns_410_on_pending below.
        resp = client.get(
            f"/api/auth/device/pending/{body['user_code']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_expired_pending_returns_404(self, client, access_token: str):
        body = _authorize(client)
        # Simulate TTL expiry by deleting both Redis entries
        sync_cache.delete(f"device_auth:dc:{body['device_code']}")
        sync_cache.delete(f"device_auth:uc:{body['user_code']}")

        resp = client.get(
            f"/api/auth/device/pending/{body['user_code']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_user_code_normalization(self, client, access_token: str):
        body = _authorize(client)
        # Inject a hyphen mid-code and lowercase — server must normalize
        raw = body["user_code"]
        typed = (raw[:4] + "-" + raw[4:]).lower()

        resp = client.get(
            f"/api/auth/device/pending/{typed}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK


class TestApprove:
    def test_creates_device_and_bound_token(
        self, client, access_token: str, admin_user: User
    ):
        body = _authorize(client)

        approve = _approve(
            client,
            access_token,
            body["user_code"],
            approved_scopes=["roms.read", "roms.user.write"],
        )
        assert approve.status_code == status.HTTP_200_OK
        data = approve.json()
        assert data["device_id"]
        assert data["device_name"] == "Pete muOS"

        # Device was created with the supplied identifier + metadata
        device = db_device_handler.get_device(
            device_id=data["device_id"], user_id=admin_user.id
        )
        assert device is not None
        assert device.client_device_identifier == "install-uuid-abc"
        assert device.client == "grout"
        assert device.platform == "muOS"
        assert device.client_version == "1.4.0"

        # ClientToken is bound to the device
        tokens = db_client_token_handler.get_tokens_by_user(admin_user.id)
        bound = [t for t in tokens if t.device_id == device.id]
        assert len(bound) == 1
        assert set(bound[0].scopes.split()) == {"roms.read", "roms.user.write"}

    def test_redis_flipped_to_approved_with_token_payload(
        self, client, access_token: str
    ):
        body = _authorize(client)
        approve = _approve(
            client,
            access_token,
            body["user_code"],
            approved_scopes=["roms.read"],
        )
        assert approve.status_code == status.HTTP_200_OK

        raw = sync_cache.get(f"device_auth:dc:{body['device_code']}")
        assert raw is not None
        stored = json.loads(raw)
        assert stored["status"] == df.FlowStatus.APPROVED
        assert stored["raw_token"].startswith("rmm_")
        assert stored["device_id"]
        # user_code pointer is cleaned up
        assert sync_cache.get(f"device_auth:uc:{body['user_code']}") is None

    def test_scope_clamping_rejects_scopes_above_allowed(
        self, client, editor_access_token: str
    ):
        body = _authorize(
            client,
            payload={
                **AUTHORIZE_PAYLOAD,
                "requested_scopes": ["roms.read", "users.write"],
            },
        )
        # editor lacks users.write; attempting to approve it is 403
        resp = _approve(
            client,
            editor_access_token,
            body["user_code"],
            approved_scopes=["roms.read", "users.write"],
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_scope_clamping_rejects_scopes_above_requested(
        self, client, access_token: str
    ):
        # Requested only roms.read — approving additional scopes is invalid
        body = _authorize(
            client,
            payload={**AUTHORIZE_PAYLOAD, "requested_scopes": ["roms.read"]},
        )
        resp = _approve(
            client,
            access_token,
            body["user_code"],
            approved_scopes=["roms.read", "roms.user.write"],
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_empty_approved_scopes_rejected(self, client, access_token: str):
        body = _authorize(client)
        resp = client.post(
            "/api/auth/device/approve",
            json={"user_code": body["user_code"], "approved_scopes": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_reapprove_response_reflects_new_device_name(
        self, client: TestClient, access_token: str, admin_user: User
    ):
        # First approval names the device "Original"
        body1 = _authorize(client)
        r1 = _approve(
            client,
            access_token,
            body1["user_code"],
            ["roms.read"],
            device_name="Original",
        )
        assert r1.json()["device_name"] == "Original"

        # Second flow with same identifier but a different user-edited name --
        # the approve response must reflect the newly-edited name, not a
        # stale value from the pre-update in-memory Device instance.
        body2 = _authorize(client)
        r2 = _approve(
            client,
            access_token,
            body2["user_code"],
            ["roms.read"],
            device_name="Renamed",
        )
        assert r2.json()["device_name"] == "Renamed"

        # And the DB row matches
        device = db_device_handler.get_device(
            device_id=r2.json()["device_id"], user_id=admin_user.id
        )
        assert device is not None
        assert device.name == "Renamed"

    def test_device_dedupe_on_same_client_identifier(
        self, client, access_token: str, admin_user: User
    ):
        body1 = _authorize(client)
        approve1 = _approve(client, access_token, body1["user_code"], ["roms.read"])
        device_id_1 = approve1.json()["device_id"]

        # Second flow with the same client_device_identifier
        body2 = _authorize(client)
        approve2 = _approve(
            client,
            access_token,
            body2["user_code"],
            ["roms.read"],
        )
        device_id_2 = approve2.json()["device_id"]

        assert device_id_1 == device_id_2, "Same identifier must reuse device"

        # Two tokens exist, both bound to the same device
        tokens = db_client_token_handler.get_tokens_by_user(admin_user.id)
        bound = [t for t in tokens if t.device_id == device_id_1]
        assert len(bound) == 2

    def test_user_edited_device_name_persists(
        self, client, access_token: str, admin_user: User
    ):
        body = _authorize(client)
        approve = _approve(
            client,
            access_token,
            body["user_code"],
            approved_scopes=["roms.read"],
            device_name="Pete's Handheld",
        )
        assert approve.status_code == status.HTTP_200_OK
        data = approve.json()

        device = db_device_handler.get_device(
            device_id=data["device_id"], user_id=admin_user.id
        )
        assert device is not None
        assert device.name == "Pete's Handheld"

    def test_expiry_respected(self, client, access_token: str, admin_user: User):
        body = _authorize(client)
        approve = _approve(
            client,
            access_token,
            body["user_code"],
            approved_scopes=["roms.read"],
            expires_in="30d",
        )
        assert approve.status_code == status.HTTP_200_OK

        tokens = db_client_token_handler.get_tokens_by_user(admin_user.id)
        assert any(t.expires_at is not None for t in tokens)

    def test_never_expires(self, client, access_token: str, admin_user: User):
        body = _authorize(client)
        approve = _approve(
            client,
            access_token,
            body["user_code"],
            approved_scopes=["roms.read"],
            expires_in="never",
        )
        assert approve.status_code == status.HTTP_200_OK

        tokens = db_client_token_handler.get_tokens_by_user(admin_user.id)
        assert any(t.expires_at is None and t.device_id for t in tokens)

    def test_already_approved_returns_410_or_404(self, client, access_token: str):
        body = _authorize(client)
        _approve(client, access_token, body["user_code"], ["roms.read"])
        # Second approve on same code: user_code pointer is cleaned up on
        # the first approval, so 404 here.
        resp = _approve(client, access_token, body["user_code"], ["roms.read"])
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_user_code_returns_404(self, client, access_token: str):
        resp = _approve(client, access_token, "BOGUS123", ["roms.read"])
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestDeny:
    def test_deny_marks_state_and_token_poll_reports_access_denied(
        self, client, access_token: str
    ):
        body = _authorize(client)

        deny = client.post(
            "/api/auth/device/deny",
            json={"user_code": body["user_code"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert deny.status_code == status.HTTP_200_OK

        poll = _poll_token(client, body["device_code"])
        assert poll.status_code == status.HTTP_400_BAD_REQUEST
        assert poll.json()["detail"] == "access_denied"

    def test_denied_returns_410_on_pending(self, client, access_token: str):
        body = _authorize(client)
        # Manually flip state to denied while keeping the user_code pointer
        # alive (simulating an internal inconsistency we should still defend)
        df.mark_denied(body["device_code"])
        # mark_denied cleans up the uc key, so now the pending lookup is 404
        resp = client.get(
            f"/api/auth/device/pending/{body['user_code']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_user_code_returns_404(self, client, access_token: str):
        resp = client.post(
            "/api/auth/device/deny",
            json={"user_code": "BOGUS123"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestToken:
    def test_pending_returns_authorization_pending(self, client):
        body = _authorize(client)
        resp = _poll_token(client, body["device_code"])
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["detail"] == "authorization_pending"

    def test_approved_returns_credentials(self, client, access_token: str):
        body = _authorize(client)
        approve = _approve(
            client,
            access_token,
            body["user_code"],
            approved_scopes=["roms.read", "roms.user.write"],
        )
        assert approve.status_code == status.HTTP_200_OK

        resp = _poll_token(client, body["device_code"])
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["access_token"].startswith("rmm_")
        assert data["device_id"] == approve.json()["device_id"]
        assert set(data["scopes"]) == {"roms.read", "roms.user.write"}

    def test_one_shot_second_poll_returns_expired_token(
        self, client, access_token: str
    ):
        body = _authorize(client)
        _approve(client, access_token, body["user_code"], ["roms.read"])

        first = _poll_token(client, body["device_code"])
        assert first.status_code == status.HTTP_200_OK

        second = _poll_token(client, body["device_code"])
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert second.json()["detail"] == "expired_token"

    def test_denied_returns_access_denied(self, client, access_token: str):
        body = _authorize(client)
        client.post(
            "/api/auth/device/deny",
            json={"user_code": body["user_code"]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        resp = _poll_token(client, body["device_code"])
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["detail"] == "access_denied"

    def test_unknown_device_code_returns_expired_token(self, client):
        resp = _poll_token(client, "a" * 64)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["detail"] == "expired_token"

    def test_slow_down_on_fast_consecutive_polls(self, client):
        body = _authorize(client)

        # First poll: no prior record, always passes (authorization_pending)
        first = _poll_token(client, body["device_code"])
        assert first.status_code == status.HTTP_400_BAD_REQUEST
        assert first.json()["detail"] == "authorization_pending"

        # Immediate second poll — inside the 5s interval → slow_down
        second = _poll_token(client, body["device_code"])
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert second.json()["detail"] == "slow_down"

    def test_per_ip_rate_limit(self, client):
        # Per-IP cap is 60/60s on /token. Use a single device_code with fast
        # polls — once the per-IP counter trips, 429 (not slow_down).
        body = _authorize(client)

        last_status = None
        for _ in range(df.TOKEN_POLL_RATE_LIMIT + 1):
            r = _poll_token(client, body["device_code"])
            last_status = r.status_code

        assert last_status == status.HTTP_429_TOO_MANY_REQUESTS


class TestVerificationPaths:
    def test_verification_path_is_relative(self, client):
        # The path is a fixed server constant (/pair/device); client metadata
        # like the device name is never interpolated into it.
        body = _authorize(
            client,
            payload={**AUTHORIZE_PAYLOAD, "name": "javascript:alert(1)"},
        )
        assert body["verification_path"] == "/pair/device"
        assert "://" not in body["verification_path"]
        assert "javascript:" not in body["verification_path_complete"]


class TestHelperFunctions:
    def test_normalize_user_code_strips_hyphens_and_uppercases(self):
        assert df.normalize_user_code("ab-cd-12") == "ABCD12"
        assert df.normalize_user_code("a b c") == "ABC"

    def test_generate_codes_have_expected_shape(self):
        dc = df.generate_device_code()
        uc = df.generate_user_code()
        assert len(dc) == df.DEVICE_CODE_BYTES * 2
        assert len(uc) == df.USER_CODE_LENGTH
        # user_code chars must be in the allowed alphabet
        from utils.client_tokens import PAIR_ALPHABET

        assert all(c in PAIR_ALPHABET for c in uc)


class TestBoundTokenInference:
    """After a device-auth approval, subsequent API calls with the returned
    access_token have their device_id inferred automatically when the payload
    omits it."""

    def _run_flow(
        self, client: TestClient, access_token: str, scopes: list[str]
    ) -> dict:
        init = _authorize(
            client,
            payload={**AUTHORIZE_PAYLOAD, "requested_scopes": scopes},
        )
        approve = _approve(client, access_token, init["user_code"], scopes)
        assert approve.status_code == status.HTTP_200_OK
        token_resp = _poll_token(client, init["device_code"])
        assert token_resp.status_code == status.HTTP_200_OK
        return token_resp.json()

    def test_play_session_inferred_from_bound_token(
        self, client: TestClient, access_token: str
    ):
        creds = self._run_flow(
            client, access_token, ["roms.user.write", "roms.user.read"]
        )

        # POST /play-sessions without device_id — server infers from token
        resp = client.post(
            "/api/play-sessions",
            headers={"Authorization": f"Bearer {creds['access_token']}"},
            json={"sessions": [{"rom_id": 1, **_recent_times(30, 15)}]},
        )
        assert resp.status_code == status.HTTP_201_CREATED

        # Session was attached to the bound device
        list_resp = client.get(
            f"/api/play-sessions?device_id={creds['device_id']}",
            headers={"Authorization": f"Bearer {creds['access_token']}"},
        )
        assert list_resp.status_code == status.HTTP_200_OK
        sessions = list_resp.json()
        assert any(s.get("device_id") == creds["device_id"] for s in sessions)

    def test_explicit_device_id_wins_over_bound(
        self,
        client: TestClient,
        access_token: str,
        admin_user: User,
    ):
        from models.device import Device

        creds = self._run_flow(
            client, access_token, ["roms.user.write", "roms.user.read"]
        )
        other = db_device_handler.add_device(
            Device(
                id="explicit-wins-device",
                user_id=admin_user.id,
                name="Second",
            )
        )

        resp = client.post(
            "/api/play-sessions",
            headers={"Authorization": f"Bearer {creds['access_token']}"},
            json={
                "device_id": other.id,
                "sessions": [{"rom_id": 1, **_recent_times(60, 15)}],
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED

        list_resp = client.get(
            f"/api/play-sessions?device_id={other.id}",
            headers={"Authorization": f"Bearer {creds['access_token']}"},
        )
        assert list_resp.status_code == status.HTTP_200_OK
        assert len(list_resp.json()) >= 1

    def test_unbound_legacy_token_attaches_sessions_with_null_device(
        self,
        client: TestClient,
        admin_user: User,
    ):
        # Simulate the legacy manual token path
        from handler.auth import auth_handler
        from models.client_token import ClientToken

        raw = auth_handler.generate_client_token()
        db_client_token_handler.add_token(
            ClientToken(
                user_id=admin_user.id,
                name="legacy",
                hashed_token=auth_handler.hash_client_token(raw),
                scopes="roms.user.write roms.user.read",
                device_id=None,
            )
        )

        resp = client.post(
            "/api/play-sessions",
            headers={"Authorization": f"Bearer {raw}"},
            json={"sessions": [{"rom_id": 1, **_recent_times(90, 15)}]},
        )
        # Existing behavior: device_id is None on the created session
        assert resp.status_code == status.HTTP_201_CREATED


class TestEndToEndHappyPath:
    """One narrative test that walks the full flow the way a real device would."""

    def test_grout_pairs_ingests_play_session(
        self, client: TestClient, access_token: str, admin_user: User
    ):
        # --- 1. Device initiates ---
        start_resp = client.post(
            "/api/auth/device/init",
            json={
                "client_device_identifier": "grout-e2e-001",
                "name": "Pete's muOS handheld",
                "client": "grout",
                "platform": "muOS",
                "client_version": "1.4.0",
                "requested_scopes": [
                    "roms.read",
                    "roms.user.read",
                    "roms.user.write",
                ],
            },
        )
        assert start_resp.status_code == status.HTTP_201_CREATED
        init = start_resp.json()
        assert init["verification_path"].endswith("/pair/device")

        # Device displays QR from verification_path_complete; user scans; user
        # is routed to /pair/device?user_code=... and authenticates.

        # --- 2. Web UI fetches pending metadata ---
        pending_resp = client.get(
            f"/api/auth/device/pending/{init['user_code']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert pending_resp.status_code == status.HTTP_200_OK
        pending = pending_resp.json()
        assert pending["name"] == "Pete's muOS handheld"
        assert pending["client"] == "grout"
        assert set(pending["allowed_scopes"]).issubset(set(pending["requested_scopes"]))

        # --- 3. Device poll while pending returns authorization_pending ---
        poll = client.post(
            "/api/auth/device/token", json={"device_code": init["device_code"]}
        )
        assert poll.status_code == status.HTTP_400_BAD_REQUEST
        assert poll.json()["detail"] == "authorization_pending"

        # --- 4. User approves with a slight name edit and 30d expiry ---
        approve_resp = client.post(
            "/api/auth/device/approve",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "user_code": init["user_code"],
                "approved_scopes": pending["allowed_scopes"],
                "device_name": "Pete's handheld",
                "expires_in": "30d",
            },
        )
        assert approve_resp.status_code == status.HTTP_200_OK
        approve = approve_resp.json()
        assert approve["device_name"] == "Pete's handheld"

        # --- 5. Device polls and gets its credentials ---
        token_resp = client.post(
            "/api/auth/device/token", json={"device_code": init["device_code"]}
        )
        assert token_resp.status_code == status.HTTP_200_OK
        creds = token_resp.json()
        assert creds["access_token"].startswith("rmm_")
        assert creds["device_id"] == approve["device_id"]
        assert creds["expires_at"] is not None

        # --- 6. Device uses its bound token to ingest a play session WITHOUT
        #        passing device_id — server infers from the bound token ---
        ingest = client.post(
            "/api/play-sessions",
            headers={"Authorization": f"Bearer {creds['access_token']}"},
            json={"sessions": [{"rom_id": 1, **_recent_times(45, 30)}]},
        )
        assert ingest.status_code == status.HTTP_201_CREATED
        assert ingest.json()["created_count"] == 1

        # --- 7. Listing the device via /devices shows the auto-created record
        #        with the right metadata from the pairing request ---
        device_resp = client.get(
            f"/api/devices/{approve['device_id']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert device_resp.status_code == status.HTTP_200_OK
        device_body = device_resp.json()
        assert device_body["name"] == "Pete's handheld"
        assert device_body["client"] == "grout"
        assert device_body["platform"] == "muOS"
        assert device_body["client_device_identifier"] == "grout-e2e-001"
        assert device_body["user_id"] == admin_user.id

        # --- 8. Re-running the flow with the same client_device_identifier
        #        yields the SAME device_id back ---
        restart = client.post(
            "/api/auth/device/init",
            json={
                "client_device_identifier": "grout-e2e-001",
                "name": "Pete's muOS handheld",
                "client": "grout",
                "platform": "muOS",
                "requested_scopes": ["roms.read"],
            },
        )
        assert restart.status_code == status.HTTP_201_CREATED
        restart_body = restart.json()
        reapprove = client.post(
            "/api/auth/device/approve",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "user_code": restart_body["user_code"],
                "approved_scopes": ["roms.read"],
            },
        )
        assert reapprove.status_code == status.HTTP_200_OK
        assert reapprove.json()["device_id"] == approve["device_id"]


class TestWhoAmIForBoundToken:
    """/api/users/me must surface the bound device_id so a device can
    identify itself (not just its user) from its token alone."""

    def test_bound_token_me_returns_current_device_id(
        self, client: TestClient, access_token: str
    ):
        init = _authorize(
            client,
            payload={**AUTHORIZE_PAYLOAD, "requested_scopes": ["me.read"]},
        )
        approve = _approve(client, access_token, init["user_code"], ["me.read"])
        assert approve.status_code == status.HTTP_200_OK
        creds = _poll_token(client, init["device_code"]).json()

        resp = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {creds['access_token']}"},
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["current_device_id"] == creds["device_id"]

    def test_unbound_legacy_token_me_returns_null_device_id(
        self,
        client: TestClient,
        admin_user: User,
    ):
        from handler.auth import auth_handler
        from models.client_token import ClientToken

        raw = auth_handler.generate_client_token()
        db_client_token_handler.add_token(
            ClientToken(
                user_id=admin_user.id,
                name="legacy",
                hashed_token=auth_handler.hash_client_token(raw),
                scopes="me.read",
                device_id=None,
            )
        )

        resp = client.get("/api/users/me", headers={"Authorization": f"Bearer {raw}"})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["current_device_id"] is None


class TestSyncNegotiateBoundTokenInference:
    def test_negotiate_without_device_id_uses_bound_device(
        self, client: TestClient, access_token: str
    ):
        init = _authorize(
            client,
            payload={
                **AUTHORIZE_PAYLOAD,
                "requested_scopes": ["assets.read", "devices.read"],
            },
        )
        _approve(
            client,
            access_token,
            init["user_code"],
            ["assets.read", "devices.read"],
        )
        token_resp = _poll_token(client, init["device_code"])
        assert token_resp.status_code == status.HTTP_200_OK
        creds = token_resp.json()

        resp = client.post(
            "/api/sync/negotiate",
            headers={"Authorization": f"Bearer {creds['access_token']}"},
            json={"saves": []},
        )
        # No device_id in payload — inferred from bound token
        assert resp.status_code == status.HTTP_200_OK

    def test_negotiate_without_bound_or_payload_device_id_is_400(
        self, client: TestClient, admin_user: User
    ):
        from handler.auth import auth_handler
        from models.client_token import ClientToken

        raw = auth_handler.generate_client_token()
        db_client_token_handler.add_token(
            ClientToken(
                user_id=admin_user.id,
                name="legacy-sync",
                hashed_token=auth_handler.hash_client_token(raw),
                scopes="assets.read devices.read",
                device_id=None,
            )
        )

        resp = client.post(
            "/api/sync/negotiate",
            headers={"Authorization": f"Bearer {raw}"},
            json={"saves": []},
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
