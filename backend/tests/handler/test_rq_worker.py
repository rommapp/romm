import logging
import sqlite3
import sys
from collections.abc import Iterator
from dataclasses import replace
from unittest.mock import MagicMock, call

import pytest
import rq.scheduler
from fakeredis import FakeRedis
from rq.exceptions import AbandonedJobError
from sqlalchemy import create_engine, event

from handler.rq_worker import (
    _DATABASE_MODULE,
    PreloadingWorker,
    RomMWorker,
    _DropPeriodicNoiseFilter,
)
from tasks.registry import REAP_STREAMING_SESSIONS_SPEC
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


@pytest.fixture
def engine(mocker):
    """Patches the real module, so the worker's lookup breaks loudly if it moves."""
    return mocker.patch(f"{_DATABASE_MODULE}.sync_engine")


@pytest.mark.parametrize("result", [True, False])
def test_job_disposes_database_pool_before_returning(mocker, engine, result) -> None:
    perform = mocker.patch("rq.Worker.perform_job", return_value=result)
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))
    job, queue = MagicMock(), MagicMock()

    assert worker.perform_job(job, queue) is result

    perform.assert_called_once_with(job, queue)
    assert engine.dispose.call_args_list == [call(close=False), call()]


def test_job_disposes_database_pool_when_perform_raises(mocker, engine) -> None:
    error = RuntimeError("job failed")
    mocker.patch("rq.Worker.perform_job", side_effect=error)
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))

    with pytest.raises(RuntimeError) as caught:
        worker.perform_job(MagicMock(), MagicMock())

    assert caught.value is error
    assert engine.dispose.call_args_list == [call(close=False), call()]


def test_job_closes_only_the_connections_it_opened(mocker, tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'romm.db'}")
    mocker.patch(f"{_DATABASE_MODULE}.sync_engine", engine)
    connections: list[sqlite3.Connection] = []
    event.listen(engine, "connect", lambda dbapi, _: connections.append(dbapi))
    # Pooled by the worker before the fork, as a failure callback does.
    engine.connect().close()

    def perform_job(job, queue) -> bool:
        engine.connect().close()
        return True

    mocker.patch("rq.Worker.perform_job", side_effect=perform_job)
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))

    assert worker.perform_job(MagicMock(), MagicMock()) is True

    inherited, opened = connections
    assert inherited.execute("SELECT 1").fetchone() == (1,)
    with pytest.raises(sqlite3.ProgrammingError):
        opened.execute("SELECT 1")
    inherited.close()


def test_job_without_database_does_not_import_it(mocker, monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, _DATABASE_MODULE, raising=False)
    mocker.patch("rq.Worker.perform_job", return_value=True)
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))

    assert worker.perform_job(MagicMock(), MagicMock()) is True

    assert _DATABASE_MODULE not in sys.modules


@pytest.mark.parametrize("job_error", [None, RuntimeError("job failed")])
def test_cleanup_failure_does_not_replace_job_outcome(
    mocker, engine, job_error
) -> None:
    engine.dispose.side_effect = [None, RuntimeError("cleanup failed")]
    mocker.patch("rq.Worker.perform_job", return_value=True, side_effect=job_error)
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))
    log = mocker.patch.object(worker.log, "exception")

    if job_error is None:
        assert worker.perform_job(MagicMock(), MagicMock()) is True
    else:
        with pytest.raises(RuntimeError) as caught:
            worker.perform_job(MagicMock(), MagicMock())
        assert caught.value is job_error

    log.assert_called_once_with("Could not close the work horse database pool")


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


class TestPreloadingWorker:
    @pytest.fixture
    def get_task(self, mocker):
        def spec(queue_name: str, enabled: bool):
            return replace(
                REAP_STREAMING_SESSIONS_SPEC, queue_name=queue_name, enabled=enabled
            )

        mocker.patch(
            "tasks.registry.SCHEDULED_TASKS",
            {
                "on": spec("streaming", True),
                "off": spec("streaming", False),
                "elsewhere": spec("low", True),
            },
        )
        return mocker.patch("tasks.registry.get_task")

    def test_imports_the_enabled_tasks_of_its_queues(self, get_task) -> None:
        PreloadingWorker(["streaming"], connection=FakeRedis(version=7))

        get_task.assert_called_once_with("on")

    def test_imports_nothing_for_a_queue_without_tasks(self, get_task) -> None:
        PreloadingWorker(["scans"], connection=FakeRedis(version=7))

        get_task.assert_not_called()
