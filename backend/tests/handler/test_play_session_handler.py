import uuid
from collections.abc import Iterator

import pytest
from rq import Queue, SimpleWorker

from handler import play_session_handler
from handler.play_session_handler import queue_ra_progress_sync
from handler.redis_handler import redis_client
from tasks.registry import SYNC_RETROACHIEVEMENTS_PROGRESS_SPEC

JOB_PATH = "tasks.scheduled.sync_retroachievements_progress"


@pytest.fixture
def queue(mocker) -> Iterator[Queue]:
    queue = Queue(name=f"test-ra-sync-{uuid.uuid4().hex}", connection=redis_client)
    mocker.patch.object(play_session_handler, "low_prio_queue", queue)
    yield queue
    for job in queue.jobs:
        job.delete()


@pytest.fixture
def user_ids() -> tuple[int, int]:
    """Ids no other test queues a sync for, as the job ids live in a shared Redis."""
    first = uuid.uuid4().int % 10**9
    return first, first + 1


def run_queued_jobs(queue: Queue) -> None:
    SimpleWorker([queue], connection=redis_client).work(burst=True)


class TestQueueRAProgressSync:
    def test_one_sync_per_user_is_queued_at_a_time(
        self, queue: Queue, user_ids: tuple[int, int]
    ):
        first, second = user_ids
        assert queue_ra_progress_sync(first, refresh_all=True)
        assert queue_ra_progress_sync(first)
        assert queue_ra_progress_sync(second)

        assert sorted(
            (job.kwargs["user_id"], job.kwargs["refresh_all"]) for job in queue.jobs
        ) == [(first, True), (second, False)]
        assert {job.timeout for job in queue.jobs} == {
            SYNC_RETROACHIEVEMENTS_PROGRESS_SPEC.timeout
        }

    @pytest.mark.parametrize("fails", [False, True], ids=["synced", "sync_failed"])
    def test_a_finished_sync_lets_the_next_play_queue_another(
        self, queue: Queue, mocker, fails: bool, user_ids: tuple[int, int]
    ):
        user_id, _ = user_ids
        sync = mocker.patch(
            f"{JOB_PATH}._sync_user_progress_by_id",
            side_effect=RuntimeError("RetroAchievements is down") if fails else None,
        )
        queue_ra_progress_sync(user_id)
        run_queued_jobs(queue)

        queue_ra_progress_sync(user_id)

        sync.assert_called_once_with(user_id, refresh_all=False)
        assert [job.kwargs["user_id"] for job in queue.jobs] == [user_id]

    def test_a_sync_that_cannot_be_queued_is_reported(self, queue: Queue, mocker):
        mocker.patch.object(
            queue, "enqueue", side_effect=ConnectionError("Redis is down")
        )

        assert not queue_ra_progress_sync(1)
