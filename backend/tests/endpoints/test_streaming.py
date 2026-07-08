import asyncio
import logging
from datetime import timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from main import app

from config import LIBRARY_BASE_PATH, OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth import oauth_handler
from handler.database import db_platform_handler, db_rom_handler
from handler.redis_handler import async_cache
from models.platform import Platform
from models.rom import Rom
from models.user import User


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clear_streaming_sessions():
    """Streaming sessions live in Redis (fakeredis under pytest) - start clean."""
    asyncio.run(async_cache.flushall())
    yield


@pytest.fixture
def access_token(admin_user: User):
    return oauth_handler.create_access_token(
        data={
            "sub": admin_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(admin_user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )


@pytest.fixture
def viewer_access_token(viewer_user: User):
    return oauth_handler.create_access_token(
        data={
            "sub": viewer_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(viewer_user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )


def _mock_cm(enabled=True, containers=None):
    """Return a mock config_manager that yields the given streaming config."""
    if containers is None:
        containers = []
    cfg = MagicMock()
    cfg.STREAMING_ENABLED = enabled
    cfg.STREAMING_CONTAINERS = containers
    return cfg


def _container_for(rom: Rom, broker_host="http://192.168.1.10:8000"):
    return {
        "platform": rom.platform_slug,
        "host": "http://192.168.1.10:3000",
        "broker_host": broker_host,
    }


def _claim(client, token, rom_id):
    return client.post(
        "/api/streaming/sessions",
        json={"rom_id": rom_id},
        headers={"Authorization": f"Bearer {token}"},
    )


# ── /config ───────────────────────────────────────────────────────────────────


def test_get_config_requires_auth(client):
    assert client.get("/api/streaming/config").status_code == 403


def test_get_config_warns_on_missing_platform(client, access_token, caplog):
    # The "romm" logger has propagate=False, so caplog's handler must be
    # added directly to it rather than relying on root-logger propagation.
    bad_container = {"host": "http://192.168.1.10:3000"}  # no "platform"
    romm_logger = logging.getLogger("romm")
    romm_logger.addHandler(caplog.handler)
    try:
        with patch(
            "endpoints.streaming.cm.get_config",
            return_value=_mock_cm(containers=[bad_container]),
        ):
            with caplog.at_level(logging.WARNING, logger="romm"):
                response = client.get(
                    "/api/streaming/config",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
    finally:
        romm_logger.removeHandler(caplog.handler)
    assert response.status_code == 200
    assert response.json()["containers"] == []
    assert "missing platform/host" in caplog.text


# ── Claiming ──────────────────────────────────────────────────────────────────


def test_claim_derives_rom_path_server_side(client, access_token, rom: Rom):
    """The broker must receive a path built from the DB row, not client input."""
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch("endpoints.streaming._call_broker") as call_broker:
            r = _claim(client, access_token, rom.id)
    assert r.status_code == 200
    assert r.json()["rom_name"] == rom.name
    _, rom_path, _ = call_broker.call_args[0]
    assert rom_path == f"{LIBRARY_BASE_PATH}/{rom.full_path}"


def test_claim_unknown_rom_returns_404(client, access_token):
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[]),
    ):
        r = _claim(client, access_token, 999999)
    assert r.status_code == 404


def test_second_claim_on_same_container_rejected(client, access_token, rom: Rom):
    """The container is single-tenant: a second claim must 409 with the holder."""
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch("endpoints.streaming._call_broker"):
            r1 = _claim(client, access_token, rom.id)
            r2 = _claim(client, access_token, rom.id)
    assert r1.status_code == 200
    assert r2.status_code == 409
    assert r2.json()["detail"]["rom_name"] == rom.name


def test_claim_session_same_container_two_platforms_rejected(
    client, access_token, admin_user: User, rom: Rom
):
    """Dolphin serves ngc and wii from one broker - second claim must be 409."""
    platform2 = db_platform_handler.add_platform(
        Platform(name="p2", slug="p2_slug", fs_slug="p2_slug")
    )
    rom2 = db_rom_handler.add_rom(
        Rom(
            platform_id=platform2.id,
            name="rom2",
            slug="rom2",
            fs_name="rom2.zip",
            fs_name_no_tags="rom2",
            fs_name_no_ext="rom2",
            fs_extension="zip",
            fs_path=f"{platform2.slug}/roms",
        )
    )
    shared_broker = "http://192.168.1.10:8000"
    containers = [
        _container_for(rom, broker_host=shared_broker),
        _container_for(rom2, broker_host=shared_broker),
    ]
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=containers),
    ):
        with patch("endpoints.streaming._call_broker"):
            r1 = _claim(client, access_token, rom.id)
            r2 = _claim(client, access_token, rom2.id)
    assert r1.status_code == 200
    assert r2.status_code == 409


def test_failed_broker_launch_frees_the_claim(client, access_token, rom: Rom):
    """If the broker rejects the launch, the container must not stay claimed."""
    from fastapi import HTTPException

    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch(
            "endpoints.streaming._call_broker",
            side_effect=HTTPException(status_code=503, detail="unreachable"),
        ):
            r1 = _claim(client, access_token, rom.id)
        with patch("endpoints.streaming._call_broker"):
            r2 = _claim(client, access_token, rom.id)
    assert r1.status_code == 503
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_claim_only_one_succeeds(access_token, rom: Rom):
    """Two concurrent claims on one container: exactly one 200 and one 409."""
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch("endpoints.streaming._call_broker"):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as ac:
                headers = {"Authorization": f"Bearer {access_token}"}
                r1, r2 = await asyncio.gather(
                    ac.post(
                        "/api/streaming/sessions",
                        json={"rom_id": rom.id},
                        headers=headers,
                    ),
                    ac.post(
                        "/api/streaming/sessions",
                        json={"rom_id": rom.id},
                        headers=headers,
                    ),
                )
    assert sorted([r1.status_code, r2.status_code]) == [200, 409]


# ── Release / ownership ───────────────────────────────────────────────────────


def test_release_uses_container_key_not_platform(client, access_token, rom: Rom):
    """release_session must find the session by broker_host, not platform string."""
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch("endpoints.streaming._call_broker"):
            _claim(client, access_token, rom.id)
        with patch("endpoints.streaming._stop_broker"):
            r = client.delete(
                f"/api/streaming/sessions/{rom.platform_slug}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    assert r.status_code == 200
    assert r.json()["status"] == "released"


def test_release_by_other_user_is_forbidden(
    client, access_token, viewer_access_token, rom: Rom
):
    """A session claimed by one user cannot be released by another non-admin."""
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch("endpoints.streaming._call_broker"):
            # viewer claims the session; admin could override, a viewer cannot
            r_claim = _claim(client, access_token, rom.id)
        r = client.delete(
            f"/api/streaming/sessions/{rom.platform_slug}",
            headers={"Authorization": f"Bearer {viewer_access_token}"},
        )
    assert r_claim.status_code == 200
    assert r.status_code == 403


def test_save_state_by_other_user_is_forbidden(
    client, access_token, viewer_access_token, rom: Rom
):
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch("endpoints.streaming._call_broker"):
            _claim(client, access_token, rom.id)
        r = client.post(
            f"/api/streaming/sessions/{rom.platform_slug}/save-state",
            json={"slot": 1},
            headers={"Authorization": f"Bearer {viewer_access_token}"},
        )
    assert r.status_code == 403


def test_save_and_exit_releases_session(client, access_token, rom: Rom):
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch("endpoints.streaming._call_broker"):
            _claim(client, access_token, rom.id)
        with patch("endpoints.streaming._save_and_exit_broker", return_value=True):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 10, "wait": True},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        # Container must be claimable again after save-and-exit.
        with patch("endpoints.streaming._call_broker"):
            r2 = _claim(client, access_token, rom.id)
    assert r.status_code == 200
    assert r.json()["saved"] is True
    assert r2.status_code == 200


def test_save_and_exit_failure_still_releases_session(client, access_token, rom: Rom):
    """A failed save is reported as saved=False, but the session is still
    released - the container must not stay claimed by a dead session."""
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch("endpoints.streaming._call_broker"):
            _claim(client, access_token, rom.id)
        with patch("endpoints.streaming._save_and_exit_broker", return_value=False):
            r = client.post(
                f"/api/streaming/sessions/{rom.platform_slug}/save-and-exit",
                json={"slot": 10, "wait": True},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        with patch("endpoints.streaming._call_broker"):
            r2 = _claim(client, access_token, rom.id)
    assert r.status_code == 200
    assert r.json()["saved"] is False
    assert r2.status_code == 200


def test_force_release_all_stops_brokers(client, access_token, rom: Rom):
    """Force-release must tell each broker to stop, not just clear Redis."""
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[_container_for(rom)]),
    ):
        with patch("endpoints.streaming._call_broker"):
            _claim(client, access_token, rom.id)
        with patch("endpoints.streaming._stop_broker") as stop_broker:
            r = client.delete(
                "/api/streaming/sessions",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    assert r.status_code == 200
    assert stop_broker.call_count == 1


# ── Auth guards ───────────────────────────────────────────────────────────────


def test_claim_session_requires_auth(client):
    assert client.post("/api/streaming/sessions", json={"rom_id": 1}).status_code == 403


def test_release_session_requires_auth(client):
    assert client.delete("/api/streaming/sessions/ps2").status_code == 403


def test_force_release_all_requires_auth(client):
    assert client.delete("/api/streaming/sessions").status_code == 403


def test_list_sessions_requires_auth(client):
    assert client.get("/api/streaming/sessions").status_code == 403


def test_list_sessions_requires_admin(client, viewer_access_token):
    r = client.get(
        "/api/streaming/sessions",
        headers={"Authorization": f"Bearer {viewer_access_token}"},
    )
    assert r.status_code == 403
