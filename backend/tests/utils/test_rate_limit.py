import pytest
from fastapi import HTTPException, status

from handler.redis_handler import sync_cache
from utils.rate_limit import enforce_rate_limit

KEY = "test-rate"


def _call() -> None:
    enforce_rate_limit(KEY, max_requests=2, window_seconds=60, detail="nope")


@pytest.fixture(autouse=True)
def clear_cache():
    sync_cache.flushall()
    yield
    sync_cache.flushall()


def test_raises_once_the_cap_is_passed():
    _call()
    _call()

    with pytest.raises(HTTPException) as exc_info:
        _call()

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert exc_info.value.detail == "nope"


def test_window_is_not_extended_by_later_calls():
    _call()
    sync_cache.expire(KEY, 5)

    _call()

    assert sync_cache.ttl(KEY) <= 5


def test_a_counter_left_without_a_ttl_is_repaired():
    """An interrupted first call must not strand a counter that never expires."""
    sync_cache.set(KEY, 1)
    assert sync_cache.ttl(KEY) == -1

    _call()

    assert 0 < sync_cache.ttl(KEY) <= 60
