from unittest.mock import patch

from fastapi import status
from redis.exceptions import ConnectionError as RedisConnectionError

from handler.health_handler import _QUEUE_NAMES

CHECKS = {"database", "valkey", "worker", "migration", "library", "resources"}


def _healthy_ready(client):
    with (
        patch("handler.health_handler._count_workers", return_value=1),
        patch("handler.health_handler.os.access", return_value=True),
    ):
        return client.get("/api/health/ready")


def test_live_answers_without_dependencies(client):
    # Act
    response = client.get("/api/health/live")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok"}


def test_ready_when_every_check_passes(client):
    # Act
    response = _healthy_ready(client)

    # Assert
    body = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert set(body) == CHECKS
    assert all(body[name]["ok"] for name in CHECKS)


def test_ready_reveals_no_timings_or_versions(client):
    # Act
    body = _healthy_ready(client).json()

    # Assert
    assert "latency_ms" not in body["database"]
    assert "version" not in body
    assert "queues" not in body["worker"]


def test_ready_names_the_failing_check(client):
    # Arrange
    with (
        patch("handler.health_handler._count_workers", return_value=1),
        patch("handler.health_handler.os.access", return_value=True),
        patch(
            "handler.health_handler._probe_redis.ping",
            side_effect=RedisConnectionError(),
        ),
    ):
        # Act
        response = client.get("/api/health/ready")

    # Assert
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["valkey"] == {"ok": False, "error": "unreachable"}
    assert response.json()["database"]["ok"] is True


def test_ready_fails_without_a_worker(client):
    # Arrange
    with (
        patch("handler.health_handler._count_workers", return_value=0),
        patch("handler.health_handler.os.access", return_value=True),
    ):
        # Act
        response = client.get("/api/health/ready")

    # Assert
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["worker"] == {"ok": False, "error": "no_workers"}


def test_migration_check_fails_when_database_is_behind(client):
    # Arrange
    with (
        patch("handler.health_handler._count_workers", return_value=1),
        patch("handler.health_handler.os.access", return_value=True),
        patch("handler.health_handler._HEAD_REVISION", "not-a-revision"),
    ):
        # Act
        response = client.get("/api/health/ready")

    # Assert
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["migration"] == {"ok": False, "error": "behind"}


def test_library_check_names_an_unreadable_folder(client):
    # Arrange
    with (
        patch("handler.health_handler._count_workers", return_value=1),
        patch("handler.health_handler.os.access", return_value=False),
    ):
        # Act
        response = client.get("/api/health/ready")

    # Assert
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["library"] == {
        "ok": False,
        "readable": False,
        "error": "unreadable",
    }


def test_status_requires_a_login(client):
    # Act
    response = client.get("/api/health/status")

    # Assert
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_status_shows_timings_and_queues_to_an_admin(client, headers):
    # Act
    response = client.get("/api/health/status", headers=headers)

    # Assert
    body = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert "version" not in body
    assert isinstance(body["database"]["latency_ms"], int)
    assert set(body["worker"]["queues"]) == set(_QUEUE_NAMES)


def test_metrics_is_off_by_default(client):
    # Act
    response = client.get("/api/health/metrics")

    # Assert
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_metrics_text_lists_every_check():
    # Arrange
    from handler.health_handler import metrics_text

    # Act
    text = metrics_text()

    # Assert
    assert 'romm_health_check_ok{check="database"}' in text
    assert 'romm_queue_depth{queue="scans"}' in text


def test_timed_checks_run_side_by_side():
    # Arrange
    import time

    from handler.health_handler import status_report

    def slow(result):
        def run():
            time.sleep(0.5)
            return result

        return run

    ok = {"ok": True, "latency_ms": 0, "error": None}
    worker = {**ok, "workers": 1, "queues": {}}
    with (
        patch("handler.health_handler._database_check", slow(ok)),
        patch("handler.health_handler._valkey_check", slow(ok)),
        patch("handler.health_handler._worker_check", slow(worker)),
        patch("handler.health_handler._migration_check", slow(ok)),
        patch("handler.health_handler.os.access", return_value=True),
    ):
        # Act
        started = time.perf_counter()
        status_report()
        elapsed = time.perf_counter() - started

    # Assert
    assert elapsed < 1.5


def test_probe_connections_give_up_quickly():
    # Arrange
    from handler.health_handler import (
        PROBE_TIMEOUT_SECONDS,
        _probe_redis,
        _worker_check,
    )

    # Act
    _worker_check()
    kwargs = _probe_redis.connection_pool.connection_kwargs

    # Assert
    assert kwargs["socket_timeout"] == PROBE_TIMEOUT_SECONDS
    assert kwargs["socket_connect_timeout"] == PROBE_TIMEOUT_SECONDS
