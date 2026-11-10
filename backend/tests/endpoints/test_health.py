from unittest.mock import patch

from fastapi import status
from redis.exceptions import ConnectionError as RedisConnectionError

READY_CHECKS = {"database", "valkey", "worker", "library", "resources"}


def test_live_answers_without_dependencies(client):
    # Act
    response = client.get("/api/health/live")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_ready_when_every_check_passes(client):
    # Arrange
    with (
        patch("endpoints.health.Worker.all", return_value=[object()]),
        patch("endpoints.health.os.access", return_value=True),
    ):
        # Act
        response = client.get("/api/health/ready")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert set(response.json()) == READY_CHECKS
    assert all(response.json().values())


def test_ready_names_the_failing_check(client):
    # Arrange
    with (
        patch("endpoints.health.Worker.all", return_value=[object()]),
        patch("endpoints.health.os.access", return_value=True),
        patch(
            "endpoints.health.redis_client.ping",
            side_effect=RedisConnectionError(),
        ),
    ):
        # Act
        response = client.get("/api/health/ready")

    # Assert
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["valkey"] is False
    assert response.json()["database"] is True


def test_ready_fails_without_a_worker(client):
    # Arrange
    with (
        patch("endpoints.health.Worker.all", return_value=[]),
        patch("endpoints.health.os.access", return_value=True),
    ):
        # Act
        response = client.get("/api/health/ready")

    # Assert
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["worker"] is False
