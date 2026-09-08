import logging
from collections.abc import Iterator

import pytest
import rq.scheduler
from fakeredis import FakeRedis

from handler.rq_worker import RomMWorker, _DropPeriodicNoiseFilter

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
