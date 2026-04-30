import logging
from unittest.mock import MagicMock, patch

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
