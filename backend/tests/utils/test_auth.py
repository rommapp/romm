from unittest.mock import AsyncMock

from handler.auth.constants import SESSION_COOKIE_NAME
from utils import auth, json_module
from utils.auth import get_session_from_environ


async def test_prefers_the_session_the_middleware_attached():
    session = {"sub": "admin", "session_id": "abc"}

    assert await get_session_from_environ({"asgi.scope": {"session": session}}) == (
        session
    )


async def test_reads_the_cookies_session_and_names_it(mocker):
    cache = mocker.patch.object(auth, "async_cache")
    cache.get = AsyncMock(return_value=json_module.dumps({"sub": "admin"}))

    session = await get_session_from_environ(
        {"HTTP_COOKIE": f"{SESSION_COOKIE_NAME}=abc"}
    )

    cache.get.assert_awaited_once_with("session:abc")
    assert session == {"sub": "admin", "session_id": "abc"}


async def test_a_cookie_for_a_missing_session_is_no_session(mocker):
    cache = mocker.patch.object(auth, "async_cache")
    cache.get = AsyncMock(return_value=None)

    assert (
        await get_session_from_environ({"HTTP_COOKIE": f"{SESSION_COOKIE_NAME}=abc"})
        == {}
    )
