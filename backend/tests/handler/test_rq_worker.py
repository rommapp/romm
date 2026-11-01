import contextlib
import logging
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import AbstractContextManager
from dataclasses import replace
from unittest.mock import MagicMock, call

import pytest
import rq.scheduler
from fakeredis import FakeRedis
from rq import Queue, Worker
from rq.exceptions import AbandonedJobError
from rq.worker import WorkerStatus
from rq.worker_registration import clean_worker_registry
from sqlalchemy import create_engine, event

from handler.redis_handler import has_live_worker
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
    """Patches the real module, so these tests fail if the engine moves or is renamed."""
    return mocker.patch(f"{_DATABASE_MODULE}.sync_engine")


def _job_outcome(job_error: Exception | None) -> AbstractContextManager[object]:
    if job_error is None:
        return contextlib.nullcontext()
    return pytest.raises(RuntimeError, match="job failed")


@pytest.mark.parametrize("job_error", [None, RuntimeError("job failed")])
def test_job_disposes_database_pool(mocker, engine, job_error) -> None:
    perform = mocker.patch(
        "rq.Worker.perform_job", return_value=True, side_effect=job_error
    )
    worker = RomMWorker(["default"], connection=FakeRedis(version=7))
    job, queue = MagicMock(), MagicMock()

    with _job_outcome(job_error):
        assert worker.perform_job(job, queue) is True

    perform.assert_called_once_with(job, queue)
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

    with _job_outcome(job_error):
        assert worker.perform_job(MagicMock(), MagicMock()) is True

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


class TestRegistrationRecovery:
    @pytest.fixture
    def worker(self) -> RomMWorker:
        worker = RomMWorker(["scans"], connection=FakeRedis(version=7))
        worker.register_birth()
        worker.set_state(WorkerStatus.IDLE)
        return worker

    def scan_worker_listening(self, worker: RomMWorker) -> bool:
        """Asks the way the scan endpoint does."""
        workers = Worker.all(connection=worker.connection)
        return has_live_worker(Queue("scans", connection=worker.connection), workers)

    @pytest.mark.parametrize("swept", [True, False])
    def test_registers_again_after_its_key_expired(
        self, worker: RomMWorker, swept: bool
    ) -> None:
        birth = worker.connection.hget(worker.key, "birth")
        worker.connection.delete(worker.key)
        if swept:
            clean_worker_registry(Queue("scans", connection=worker.connection))
        else:
            # The base heartbeat recreates the key with only last_heartbeat.
            Worker.heartbeat(worker)
        assert not self.scan_worker_listening(worker)

        worker.heartbeat()

        assert self.scan_worker_listening(worker)
        assert worker.connection.hget(worker.key, "birth") == birth
        assert worker.connection.hget(worker.key, "state") == b"idle"
        assert worker.connection.ttl(worker.key) > 0

    def test_a_registered_worker_is_left_alone(
        self, worker: RomMWorker, mocker
    ) -> None:
        register_again = mocker.patch.object(worker, "_register_again")

        worker.heartbeat()

        register_again.assert_not_called()

    def test_a_pipelined_heartbeat_does_not_register(self, worker: RomMWorker) -> None:
        worker.connection.delete(worker.key)

        with worker.connection.pipeline() as pipeline:
            worker.heartbeat(pipeline=pipeline)
            pipeline.execute()

        assert not worker.connection.hexists(worker.key, "queues")

    def test_a_worker_not_yet_born_does_not_register(self) -> None:
        worker = RomMWorker(["scans"], connection=FakeRedis(version=7))

        worker.heartbeat()

        assert not worker.connection.hexists(worker.key, "queues")
