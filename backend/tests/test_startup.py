"""Tests for startup-time auto-enqueue of the recompute task."""

import startup
from rq.job import JOB_ID_PATTERN


def test_enqueue_recompute_skips_when_no_missing_hashes(mocker) -> None:
    """Saves all have content_hash -> no enqueue."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=0
    )
    enqueue = mocker.patch.object(startup.low_prio_queue, "enqueue")

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue.assert_not_called()


def test_enqueue_recompute_fires_when_missing_hashes_present(mocker) -> None:
    """At least one Save row has NULL content_hash -> enqueue exactly once."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=42
    )
    mocker.patch.object(startup.Job, "exists", return_value=False)
    enqueue = mocker.patch.object(startup.low_prio_queue, "enqueue")

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue.assert_called_once()
    args, kwargs = enqueue.call_args
    # First positional arg is the bound task.run method
    assert args[0].__self__ is startup.recompute_save_content_hashes_task
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


def test_recompute_job_id_is_valid_rq_id() -> None:
    """RQ rejects any job_id not matching [A-Za-z0-9_-]+ (ValueError in set_id),
    which the broad except here would swallow -> backfill silently never enqueues.
    A colon was the original culprit; assert the full contract, not just that."""
    assert JOB_ID_PATTERN.fullmatch(startup.RECOMPUTE_SAVE_HASHES_JOB_ID)


def test_enqueue_recompute_skips_when_already_queued(mocker) -> None:
    """An in-flight job from a previous restart -> skip enqueue, don't double up."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=10
    )
    mocker.patch.object(startup.Job, "exists", return_value=True)
    enqueue = mocker.patch.object(startup.low_prio_queue, "enqueue")

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue.assert_not_called()


def test_enqueue_recompute_swallows_count_error(mocker) -> None:
    """A failed COUNT query must not crash startup."""
    mocker.patch.object(
        startup.db_save_handler,
        "count_saves_missing_content_hash",
        side_effect=RuntimeError("db gone"),
    )
    enqueue = mocker.patch.object(startup.low_prio_queue, "enqueue")

    startup._enqueue_recompute_save_hashes_if_needed()

    enqueue.assert_not_called()


def test_enqueue_recompute_swallows_enqueue_error(mocker) -> None:
    """A failed enqueue must not crash startup."""
    mocker.patch.object(
        startup.db_save_handler, "count_saves_missing_content_hash", return_value=5
    )
    mocker.patch.object(startup.Job, "exists", return_value=False)
    mocker.patch.object(
        startup.low_prio_queue, "enqueue", side_effect=RuntimeError("redis gone")
    )

    startup._enqueue_recompute_save_hashes_if_needed()
