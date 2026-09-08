import logging

import pytest
import rq.scheduler

from handler.rq_worker import _DropPeriodicNoiseFilter, _silence_periodic_noise


def record(message: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord("rq", logging.DEBUG, "f", 1, message, args, None)


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


def test_silencing_a_logger_is_idempotent() -> None:
    log = logging.getLogger(f"{rq.scheduler.__name__}.test")

    _silence_periodic_noise(log)
    _silence_periodic_noise(log)

    assert len(log.filters) == 1
