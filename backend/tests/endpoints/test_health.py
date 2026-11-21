from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Response, status
from fastapi.testclient import TestClient
from main import app

from endpoints.health import ready
from handler.activity_handler import activity_handler
from handler.health_handler import is_ready, mark_not_ready


@pytest.fixture(autouse=True)
def fresh_process():
    mark_not_ready()


def test_probe_answers_503_until_ready():
    response = Response()

    assert ready(response) == {"ready": False}
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_ready_once_started(client):
    response = client.get("/api/health/ready")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"ready": True}


def test_not_ready_while_starting_up():
    # Arrange
    ready_during_startup: list[bool] = []
    grace = AsyncMock(side_effect=lambda: ready_during_startup.append(is_ready()))

    # Act
    with patch("main.start_restart_grace", grace), TestClient(app) as client:
        serving = client.get("/api/health/ready")

    # Assert
    assert ready_during_startup == [False]
    assert serving.status_code == status.HTTP_200_OK


def test_not_ready_as_soon_as_shutdown_begins():
    # Arrange
    ready_during_cleanup: list[bool] = []
    flush = AsyncMock(side_effect=lambda: ready_during_cleanup.append(is_ready()))

    # Act
    with patch.object(activity_handler, "flush_refresh", flush):
        with TestClient(app) as client:
            serving = client.get("/api/health/ready")

    # Assert
    assert serving.status_code == status.HTTP_200_OK
    assert ready_during_cleanup == [False]
    assert is_ready() is False
