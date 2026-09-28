import logging
from collections.abc import Iterator
from unittest.mock import MagicMock, Mock

import pytest
import rq.scheduler
from fakeredis import FakeRedis
from rq import Worker
from rq.exceptions import AbandonedJobError

from handler.rq_worker import RomMWorker, _DropPeriodicNoiseFilter
from tasks.tasks import report_task_failure

scheduler_log = logging.getLogger(rq.scheduler.__name__)


@pytest.fixture(autouse=True)
def restore_scheduler_log_filters() -> Iterator[None]:
    """The scheduler logger is global, so a worker built here would leak into other tests."""
    original = list(scheduler_log.filters)
    yield
    scheduler_log.filters = original


def record(message: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord("rq", logging.DEBUG, "f", 1, message, args, None)


def installed_filters(logger: logging.Logger) -> list[_DropPeriodicNoiseFilter]:
    return [f for f in logger.filters if isinstance(f, _DropPeriodicNoiseFilter)]


@pytest.mark.parametrize(
    "message,args",
    [
        ("Scheduler sending heartbeat to %s", ("low, default, high",)),
        ("Cleaning registries for queue: %s", ("default",)),
    ],
)
def test_drops_periodic_noise(message: str, args: tuple[object, ...]) -> None:
    assert not _DropPeriodicNoiseFilter().filter(record(message, *args))


@pytest.mark.parametrize(
    "message,args",
    [
        ("Acquired scheduler lock for %s", ("default",)),
        ("Scheduler for %s started with PID %s", ("default", 1)),
        ("Scheduler lock for %s had expired; re-acquired", ("default",)),
    ],
)
def test_keeps_everything_else(message: str, args: tuple[object, ...]) -> None:
    assert _DropPeriodicNoiseFilter().filter(record(message, *args))


def test_worker_silences_its_own_and_the_scheduler_logger() -> None:
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))

    assert installed_filters(worker.log)
    assert installed_filters(scheduler_log)


def test_a_second_worker_does_not_stack_another_filter() -> None:
    connection = FakeRedis(version=7)
    RomMWorker(["default"], connection=connection)
    RomMWorker(["scans"], connection=connection)

    assert len(installed_filters(scheduler_log)) == 1


def test_worker_reports_failed_tasks() -> None:
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))

    assert report_task_failure in worker._exc_handlers


def test_a_killed_horse_is_reported_like_a_dead_worker(mocker) -> None:
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))
    handle_exception = mocker.patch.object(worker, "handle_exception")
    job = MagicMock()

    worker.handle_work_horse_killed(job, 123, 9, None)

    callback_args = job.execute_failure_callback.call_args.args
    exception_args = handle_exception.call_args.args
    assert callback_args[1] is AbandonedJobError
    assert exception_args[0] is job
    assert exception_args[1] is AbandonedJobError


def test_a_failing_callback_still_reaches_the_handlers(mocker) -> None:
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))
    handle_exception = mocker.patch.object(worker, "handle_exception")
    job = MagicMock()
    job.execute_failure_callback.side_effect = RuntimeError("callback broke")

    worker.handle_work_horse_killed(job, 123, 9, None)

    handle_exception.assert_called_once()


class TestFailInstallSession:
    def test_ignores_jobs_outside_the_install_queue(self, monkeypatch):
        update_session = Mock()
        monkeypatch.setattr(
            "handler.database.db_install_session_handler.update_session",
            update_session,
        )
        job = Mock(origin="default", args=[42])

        RomMWorker._fail_install_session(job)

        update_session.assert_not_called()

    def test_marks_the_session_failed_and_clears_vnc_fields(self, monkeypatch):
        update_session = Mock()
        monkeypatch.setattr(
            "handler.database.db_install_session_handler.update_session",
            update_session,
        )
        job = Mock(origin="install", args=[7])

        RomMWorker._fail_install_session(job)

        update_session.assert_called_once()
        session_id, data = update_session.call_args[0]
        assert session_id == 7
        assert data["state"] == "failed"
        assert data["vnc_url"] is None
        assert data["vnc_web_port"] is None
        assert data["error"]

    def test_swallows_a_missing_args_list_instead_of_raising(self, monkeypatch):
        update_session = Mock()
        monkeypatch.setattr(
            "handler.database.db_install_session_handler.update_session",
            update_session,
        )
        job = Mock(origin="install", args=[])

        RomMWorker._fail_install_session(job)  # must not raise

        update_session.assert_not_called()

    def test_swallows_an_update_failure_instead_of_raising(self, monkeypatch):
        monkeypatch.setattr(
            "handler.database.db_install_session_handler.update_session",
            Mock(side_effect=RuntimeError("db is down")),
        )
        job = Mock(origin="install", args=[7])

        RomMWorker._fail_install_session(job)  # must not raise


class TestHandleException:
    def test_fails_the_install_session_before_delegating_to_rq(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            RomMWorker,
            "_fail_install_session",
            staticmethod(lambda job: calls.append(("fail_install_session", job))),
        )
        monkeypatch.setattr(
            Worker,
            "handle_exception",
            lambda self, job, *exc_info: calls.append(("super", job, exc_info)),
        )

        worker = RomMWorker.__new__(RomMWorker)
        job = Mock()
        exc_info = (ValueError, ValueError("boom"), None)

        worker.handle_exception(job, *exc_info)

        assert calls == [
            ("fail_install_session", job),
            ("super", job, exc_info),
        ]
