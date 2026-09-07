"""Tests for startup-time auto-enqueue of the recompute task."""

import pytest
import startup
from rq.exceptions import DuplicateJobError
from rq.job import JOB_ID_PATTERN

from tasks.registry import get_task


@pytest.fixture
def enqueue_task(mocker):
    return mocker.patch.object(startup, "enqueue_task")


def test_enqueue_recompute_skips_when_no_missing_hashes(mocker, enqueue_task):
    """Saves all have content_hash -> no enqueue."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=0
    )

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue_task.assert_not_called()


def test_enqueue_recompute_fires_when_missing_hashes_present(mocker, enqueue_task):
    """At least one Save row has NULL content_hash -> enqueue exactly once."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=42
    )

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue_task.assert_called_once_with(
        "recompute_save_content_hashes",
        job_id=startup.RECOMPUTE_SAVE_HASHES_JOB_ID,
        # RQ settles the duplicate check and the enqueue in one round trip
        unique=True,
    )


def test_enqueue_convert_webp_fires_when_not_queued(enqueue_task):
    """No in-flight bootstrap job -> enqueue the backfill exactly once."""
    startup._enqueue_convert_images_to_webp()

    enqueue_task.assert_called_once_with(
        "convert_images_to_webp",
        job_id=startup.CONVERT_IMAGES_TO_WEBP_JOB_ID,
        unique=True,
    )


@pytest.mark.parametrize(
    "job_id",
    (startup.RECOMPUTE_SAVE_HASHES_JOB_ID, startup.CONVERT_IMAGES_TO_WEBP_JOB_ID),
)
def test_backfill_job_ids_are_valid_rq_ids(job_id):
    """RQ rejects any job_id not matching [A-Za-z0-9_-]+ (ValueError in set_id),
    which the broad except here would swallow -> backfill silently never
    enqueues. A colon was the original culprit."""
    assert JOB_ID_PATTERN.fullmatch(job_id)


def test_both_backfills_name_a_registered_task():
    """The name in the payload is all the runner gets, so it has to resolve."""
    assert get_task("recompute_save_content_hashes") is not None
    assert get_task("convert_images_to_webp") is not None


@pytest.mark.parametrize(
    "error", (DuplicateJobError("exists"), RuntimeError("redis gone"))
)
def test_a_failed_backfill_enqueue_does_not_crash_startup(mocker, error):
    """An in-flight job from a previous restart, or a Redis outage, is survivable."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=10
    )
    mocker.patch.object(startup, "enqueue_task", side_effect=error)

    startup._enqueue_recompute_save_hashes_if_needed()
    startup._enqueue_convert_images_to_webp()


def test_enqueue_recompute_swallows_count_error(mocker, enqueue_task):
    """A failed COUNT query must not crash startup."""
    mocker.patch.object(
        startup.db_save_handler,
        "count_saves_missing_content_hash",
        side_effect=RuntimeError("db gone"),
    )

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue_task.assert_not_called()


class TestDropLegacySchedulerState:
    """The old scheduler's keys go on the first start after the migration."""

    @pytest.fixture
    def redis(self, mocker):
        redis = mocker.patch.object(startup, "redis_client")
        redis.scan_iter.return_value = []
        return redis

    def test_removes_the_scheduler_keys_with_no_jobs_left_behind(self, redis):
        redis.zrange.return_value = []

        startup._drop_legacy_scheduler_state()

        redis.delete.assert_called_once_with(*startup.LEGACY_SCHEDULER_KEYS)

    def test_deletes_orphaned_jobs_but_not_queued_ones(self, mocker, redis):
        redis.zrange.return_value = [b"orphan", b"queued"]
        for queue in (startup.high_prio_queue, startup.default_queue):
            mocker.patch.object(queue, "get_job_ids", return_value=[])
        mocker.patch.object(
            startup.low_prio_queue, "get_job_ids", return_value=["queued"]
        )

        startup._drop_legacy_scheduler_state()

        assert redis.delete.call_args_list[0].args == ("rq:job:orphan",)
        assert redis.delete.call_args_list[-1].args == startup.LEGACY_SCHEDULER_KEYS

    def test_survives_a_redis_failure(self, redis):
        redis.zrange.side_effect = RuntimeError("redis gone")

        startup._drop_legacy_scheduler_state()
