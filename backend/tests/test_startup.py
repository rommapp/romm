"""Tests for startup-time auto-enqueue of the recompute task."""

import startup
from rq.exceptions import DuplicateJobError
from rq.job import JOB_ID_PATTERN

from tasks.registry import get_task


def test_enqueue_recompute_skips_when_no_missing_hashes(mocker):
    """Saves all have content_hash -> no enqueue."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=0
    )
    enqueue = mocker.patch.object(startup.low_prio_queue, "enqueue")

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue.assert_not_called()


def test_enqueue_recompute_fires_when_missing_hashes_present(mocker):
    """At least one Save row has NULL content_hash -> enqueue exactly once."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=42
    )
    enqueue = mocker.patch.object(startup.low_prio_queue, "enqueue")

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue.assert_called_once()
    args, kwargs = enqueue.call_args
    # Enqueued by name, so the payload survives the code moving underneath it
    assert args[0] is startup.run_task_by_name
    assert kwargs["kwargs"] == {"name": startup.RECOMPUTE_SAVE_HASHES_TASK}
    # RQ settles the duplicate check and the enqueue in one round trip
    assert kwargs["unique"] is True
    # Sanity-check the meta payload routes correctly in the task list UI
    assert kwargs["meta"]["task_name"] == (
        startup.recompute_save_content_hashes_task.title
    )
    assert kwargs["meta"]["task_type"] == (
        startup.recompute_save_content_hashes_task.task_type.value
    )
    # Job timeout must be passed; otherwise long-running recomputes get killed
    # by RQ's default short timeout on very large libraries.
    assert kwargs["job_timeout"] == startup.TASK_TIMEOUT
    assert kwargs["job_id"] == startup.RECOMPUTE_SAVE_HASHES_JOB_ID


def test_recompute_job_id_is_valid_rq_id():
    """RQ rejects any job_id not matching [A-Za-z0-9_-]+ (ValueError in set_id),
    which the broad except here would swallow -> backfill silently never enqueues.
    A colon was the original culprit; assert the full contract, not just that."""
    assert JOB_ID_PATTERN.fullmatch(startup.RECOMPUTE_SAVE_HASHES_JOB_ID)


def test_enqueue_recompute_tolerates_an_in_flight_job(mocker):
    """An in-flight job from a previous restart -> RQ refuses, startup carries on."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=10
    )
    mocker.patch.object(
        startup.low_prio_queue, "enqueue", side_effect=DuplicateJobError("exists")
    )

    startup._enqueue_recompute_save_hashes_if_needed()


def test_both_backfills_name_a_registered_task(mocker):
    """The name in the payload is all the runner gets, so it has to resolve."""
    assert get_task(startup.RECOMPUTE_SAVE_HASHES_TASK) is (
        startup.recompute_save_content_hashes_task
    )
    assert get_task(startup.CONVERT_IMAGES_TO_WEBP_TASK) is (
        startup.convert_images_to_webp_task
    )


def test_enqueue_recompute_swallows_count_error(mocker):
    """A failed COUNT query must not crash startup."""
    mocker.patch.object(
        startup.db_save_handler,
        "count_saves_missing_content_hash",
        side_effect=RuntimeError("db gone"),
    )
    enqueue = mocker.patch.object(startup.low_prio_queue, "enqueue")

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue.assert_not_called()


def test_enqueue_recompute_swallows_enqueue_error(mocker):
    """A failed enqueue must not crash startup."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=5
    )
    mocker.patch.object(
        startup.low_prio_queue, "enqueue", side_effect=RuntimeError("redis gone")
    )

    startup._enqueue_recompute_save_hashes_if_needed()


def test_enqueue_convert_webp_fires_when_not_queued(mocker):
    """No in-flight bootstrap job -> enqueue the backfill exactly once."""
    enqueue = mocker.patch.object(startup.low_prio_queue, "enqueue")

    startup._enqueue_convert_images_to_webp()

    enqueue.assert_called_once()
    args, kwargs = enqueue.call_args
    assert args[0] is startup.run_task_by_name
    assert kwargs["kwargs"] == {"name": startup.CONVERT_IMAGES_TO_WEBP_TASK}
    assert kwargs["unique"] is True
    assert kwargs["meta"]["task_name"] == startup.convert_images_to_webp_task.title
    assert kwargs["meta"]["task_type"] == (
        startup.convert_images_to_webp_task.task_type.value
    )
    assert kwargs["job_timeout"] == startup.TASK_TIMEOUT
    assert kwargs["job_id"] == startup.CONVERT_IMAGES_TO_WEBP_JOB_ID


def test_convert_webp_job_id_is_valid_rq_id():
    """An invalid job_id raises in set_id, which the broad except swallows ->
    backfill silently never enqueues. Assert the id matches RQ's contract."""
    assert JOB_ID_PATTERN.fullmatch(startup.CONVERT_IMAGES_TO_WEBP_JOB_ID)


def test_enqueue_convert_webp_tolerates_an_in_flight_job(mocker):
    """An in-flight job from a previous restart -> RQ refuses, startup carries on."""
    mocker.patch.object(
        startup.low_prio_queue, "enqueue", side_effect=DuplicateJobError("exists")
    )

    startup._enqueue_convert_images_to_webp()


def test_enqueue_convert_webp_swallows_enqueue_error(mocker):
    """A failed enqueue must not crash startup."""
    mocker.patch.object(
        startup.low_prio_queue, "enqueue", side_effect=RuntimeError("redis gone")
    )

    startup._enqueue_convert_images_to_webp()
