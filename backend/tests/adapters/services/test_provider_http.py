import asyncio
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from fastapi import HTTPException, status

from adapters.services import provider_http
from adapters.services.provider_http import send_with_retries, unavailable


def _status(code: int) -> aiohttp.ClientResponseError:
    return aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=code
    )


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    sleep = AsyncMock()
    monkeypatch.setattr(provider_http, "asyncio", MagicMock(wraps=asyncio, sleep=sleep))
    return sleep


async def _send(
    *outcomes: object, attempts: int = 2, backoff: float = 2
) -> tuple[object, AsyncMock]:
    send = AsyncMock(side_effect=list(outcomes))
    result = await send_with_retries(
        send, provider="Test", url="u", attempts=attempts, backoff=backoff
    )
    return result, send


def test_unavailable_names_the_provider():
    exc = unavailable("Test")

    assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc.detail == "Can't connect to Test, check your internet connection"


async def test_a_first_answer_is_returned():
    result, send = await _send("ok")

    assert result == "ok"
    assert send.await_count == 1


@pytest.mark.parametrize(
    "error",
    [TimeoutError(), aiohttp.ServerTimeoutError()],
    ids=["total", "socket"],
)
async def test_a_timeout_is_retried(error: Exception):
    result, send = await _send(error, "ok")

    assert result == "ok"
    assert send.await_count == 2


async def test_the_last_timeout_is_raised():
    with pytest.raises(TimeoutError):
        await _send(TimeoutError(), TimeoutError())


async def test_a_rate_limit_backs_off_before_retrying(no_backoff: AsyncMock):
    result, _ = await _send(_status(429), "ok", backoff=5)

    assert result == "ok"
    no_backoff.assert_awaited_once_with(5)


async def test_the_last_rate_limit_is_raised():
    with pytest.raises(aiohttp.ClientResponseError) as exc:
        await _send(_status(429), _status(429), _status(429), attempts=3)

    assert exc.value.status == 429


async def test_a_lost_connection_is_unavailable_at_once():
    send = AsyncMock(side_effect=aiohttp.ClientConnectionError())

    with pytest.raises(HTTPException) as exc:
        await send_with_retries(send, provider="Test", url="u")

    assert exc.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert send.await_count == 1


async def test_an_error_status_is_raised_without_a_retry():
    send = AsyncMock(side_effect=_status(500))

    with pytest.raises(aiohttp.ClientResponseError):
        await send_with_retries(send, provider="Test", url="u")

    assert send.await_count == 1


@pytest.mark.parametrize("retry", [True, False])
async def test_retry_on_status_decides_another_attempt(retry: bool):
    decide = AsyncMock(return_value=retry)
    send = AsyncMock(side_effect=[_status(401), "ok"])

    if retry:
        assert (
            await send_with_retries(
                send, provider="Test", url="u", retry_on_status=decide
            )
            == "ok"
        )
    else:
        with pytest.raises(aiohttp.ClientResponseError):
            await send_with_retries(
                send, provider="Test", url="u", retry_on_status=decide
            )

    assert decide.await_args is not None
    assert decide.await_args.args[0].status == 401


async def test_no_attempt_is_refused():
    with pytest.raises(ValueError):
        await send_with_retries(AsyncMock(), provider="Test", url="u", attempts=0)
