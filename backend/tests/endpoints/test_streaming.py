import asyncio
import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def _mock_cm(enabled=True, containers=None):
    """Return a mock config_manager that yields the given streaming config."""
    if containers is None:
        containers = []
    cfg = MagicMock()
    cfg.STREAMING_ENABLED = enabled
    cfg.STREAMING_CONTAINERS = containers
    return cfg


def test_get_config_warns_on_missing_platform(client, caplog):
    bad_container = {"host": "http://192.168.1.10:3000"}  # no "platform"
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[bad_container]),
    ):
        with caplog.at_level(logging.WARNING, logger="romm"):
            response = client.get("/api/streaming/config")
    assert response.status_code == 200
    assert response.json()["containers"] == []
    assert "missing platform/host" in caplog.text


@pytest.mark.skip(reason="requires db")
def test_claim_session_same_container_two_platforms_rejected(client, access_token):
    """Dolphin serves ngc and wii from the same broker — second claim must be 409."""
    containers = [
        {
            "platform": "ngc",
            "host": "http://192.168.1.10:3000",
            "broker_host": "http://192.168.1.10:8000",
        },
        {
            "platform": "wii",
            "host": "http://192.168.1.10:3000",
            "broker_host": "http://192.168.1.10:8000",
        },
    ]
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=containers),
    ):
        with patch("endpoints.streaming._call_broker"):
            r1 = client.post(
                "/api/streaming/sessions",
                json={
                    "platform": "ngc",
                    "rom_path": "/roms/game.iso",
                    "rom_name": "Game",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r2 = client.post(
                "/api/streaming/sessions",
                json={
                    "platform": "wii",
                    "rom_path": "/roms/game2.iso",
                    "rom_name": "Game2",
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
    assert r1.status_code == 200
    assert r2.status_code == 409


@pytest.mark.skip(reason="requires db")
def test_release_uses_container_key_not_platform(client, access_token):
    """release_session must find the session by broker_host, not by platform string."""
    container = {
        "platform": "ngc",
        "host": "http://192.168.1.10:3000",
        "broker_host": "http://192.168.1.10:8000",
    }
    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[container]),
    ):
        with patch("endpoints.streaming._call_broker"):
            client.post(
                "/api/streaming/sessions",
                json={"platform": "ngc", "rom_path": "/roms/g.iso", "rom_name": "G"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        r = client.delete(
            "/api/streaming/sessions/ngc",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "released"


@pytest.mark.asyncio
@pytest.mark.skip(reason="requires db")
async def test_concurrent_claim_only_one_succeeds(access_token):
    """Two concurrent claims on the same container must yield exactly one 200 and one 409."""
    container = {
        "platform": "ps2",
        "host": "http://192.168.1.20:3000",
        "broker_host": "http://192.168.1.20:8000",
    }

    with patch(
        "endpoints.streaming.cm.get_config",
        return_value=_mock_cm(containers=[container]),
    ):
        with patch("endpoints.streaming._call_broker"):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as ac:
                r1, r2 = await asyncio.gather(
                    ac.post(
                        "/api/streaming/sessions",
                        json={
                            "platform": "ps2",
                            "rom_path": "/roms/a.iso",
                            "rom_name": "A",
                        },
                        headers={"Authorization": f"Bearer {access_token}"},
                    ),
                    ac.post(
                        "/api/streaming/sessions",
                        json={
                            "platform": "ps2",
                            "rom_path": "/roms/b.iso",
                            "rom_name": "B",
                        },
                        headers={"Authorization": f"Bearer {access_token}"},
                    ),
                )

    assert sorted([r1.status_code, r2.status_code]) == [200, 409]


def test_release_session_requires_auth(client):
    """Unauthenticated DELETE /sessions/{platform} must return 403."""
    response = client.delete("/api/streaming/sessions/ps2")
    assert response.status_code == 403


def test_force_release_all_requires_auth(client):
    """Unauthenticated DELETE /sessions must return 403."""
    response = client.delete("/api/streaming/sessions")
    assert response.status_code == 403
