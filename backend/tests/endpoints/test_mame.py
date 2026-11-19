from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from tests.factories import make_platform


@pytest.fixture(autouse=True)
def worker_listening():
    with patch("endpoints.mame.has_live_worker", return_value=True) as mocked:
        yield mocked


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_match_queues_the_task(client, access_token, admin_user):
    platform = make_platform("arcade")
    job = MagicMock(id="job-1", created_at=None, enqueued_at=None)
    job.get_status.return_value = "queued"
    with patch("endpoints.mame.enqueue_task", return_value=job) as enqueue:
        response = client.post(
            "/api/mame/match",
            json={"platform_id": platform.id, "rename": False},
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["task_id"] == "job-1"
    assert enqueue.call_args.args == ("match_mame_platform",)
    assert enqueue.call_args.kwargs["task_kwargs"] == {
        "platform_id": platform.id,
        "action": "match",
        "rename": False,
    }
    assert enqueue.call_args.kwargs["run_by_user_id"] == admin_user.id


def test_match_is_for_arcade_platforms(client, access_token):
    platform = make_platform("snes")
    with patch("endpoints.mame.enqueue_task") as enqueue:
        response = client.post(
            "/api/mame/match",
            json={"platform_id": platform.id},
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    enqueue.assert_not_called()


def test_match_of_a_missing_platform(client, access_token):
    response = client.post(
        "/api/mame/match",
        json={"platform_id": 999999},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_match_without_a_worker_is_refused(client, access_token, worker_listening):
    worker_listening.return_value = False
    platform = make_platform("arcade")
    with patch("endpoints.mame.enqueue_task") as enqueue:
        response = client.post(
            "/api/mame/match",
            json={"platform_id": platform.id},
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    enqueue.assert_not_called()
