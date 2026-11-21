import io
import logging
from collections.abc import Iterator

import pytest
from fakeredis import FakeRedis

from handler import redis_handler
from logger.log_stream_handler import LOG_BUFFER_KEY, STDOUT_ONLY, LogStreamHandler


@pytest.fixture
def redis(mocker) -> FakeRedis:
    fake = FakeRedis(version=7)
    mocker.patch.object(redis_handler, "redis_client", fake)
    return fake


@pytest.fixture
def stdout() -> io.StringIO:
    return io.StringIO()


@pytest.fixture
def logger(stdout: io.StringIO) -> Iterator[logging.Logger]:
    logger = logging.getLogger("romm.tests.log_stream_handler")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handlers = [logging.StreamHandler(stdout), LogStreamHandler()]
    for handler in handlers:
        logger.addHandler(handler)
    yield logger
    for handler in handlers:
        logger.removeHandler(handler)


def test_record_reaches_the_buffer(redis: FakeRedis, logger: logging.Logger) -> None:
    logger.info("scan finished")

    buffered = redis.lrange(LOG_BUFFER_KEY, 0, -1)
    assert len(buffered) == 1
    assert b"scan finished" in buffered[0]


def test_stdout_only_record_skips_the_buffer(
    redis: FakeRedis, logger: logging.Logger, stdout: io.StringIO
) -> None:
    logger.info("secret link", extra=STDOUT_ONLY)

    assert redis.lrange(LOG_BUFFER_KEY, 0, -1) == []
    assert "secret link" in stdout.getvalue()
