from config import has_proxy_env
from utils.context import (
    create_aiohttp_session,
    create_httpx_async_client,
    create_httpx_client,
)


class TestProxyAwareHttpClients:
    def test_has_proxy_env_detects_uppercase_proxy_vars(self, monkeypatch):
        monkeypatch.setenv("HTTP_PROXY", "http://proxy.internal:8080")

        assert has_proxy_env() is True

    def test_has_proxy_env_returns_false_without_proxy_vars(self, monkeypatch):
        for var in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "NO_PROXY",
        ):
            monkeypatch.delenv(var, raising=False)

        assert has_proxy_env() is False

    async def test_create_aiohttp_session_uses_config_proxy_env(self, monkeypatch):
        monkeypatch.setattr("utils.context.has_proxy_env", lambda: True)

        session = create_aiohttp_session()

        try:
            assert session.trust_env is True
        finally:
            await session.close()

    async def test_create_httpx_clients_use_config_proxy_env(self, monkeypatch):
        monkeypatch.setattr("utils.context.has_proxy_env", lambda: True)

        async_client = create_httpx_async_client()
        client = create_httpx_client()

        try:
            assert async_client._trust_env is True
            assert client._trust_env is True
        finally:
            await async_client.aclose()
            client.close()
