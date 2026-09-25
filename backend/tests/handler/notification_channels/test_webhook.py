import asyncio
import hashlib
import hmac
import json

import httpx
import pytest

from handler.notification_channels import webhook
from handler.notification_channels.config import WebhookConfig
from handler.notification_channels.messages import OutboundMessage
from handler.notification_channels.webhook import (
    WebhookError,
    build_request,
    check_url,
    send,
)

from .fixtures import make_actor, make_notification


def _message(**overrides) -> OutboundMessage:
    return OutboundMessage(
        notification=make_notification(**overrides),
        title="Maintenance tonight",
        body="RomM restarts at 23:00",
        url="https://romm.example.com/platforms",
    )


class TestBuildRequest:
    def test_carries_the_notification_and_its_text(self):
        request = build_request(
            WebhookConfig(url="https://hooks.example.com/romm"),
            _message(actor=make_actor()),
        )

        payload = json.loads(request.content)
        assert request.url == "https://hooks.example.com/romm"
        assert payload["event"] == "notification"
        assert payload["title"] == "Maintenance tonight"
        assert payload["url"] == "https://romm.example.com/platforms"
        assert payload["actor"] == {"id": 1, "username": "admin"}
        assert webhook.SIGNATURE_HEADER not in request.headers

    def test_is_signed_with_the_secret(self):
        request = build_request(
            WebhookConfig(url="https://hooks.example.com", secret="k"),
            _message(),
        )

        expected = hmac.new(b"k", request.content, hashlib.sha256).hexdigest()
        assert request.headers[webhook.SIGNATURE_HEADER] == f"sha256={expected}"


class TestCheckUrl:
    @pytest.mark.parametrize("url", ["ftp://example.com/x", "not a url", "https://"])
    def test_refuses_anything_but_http(self, url):
        with pytest.raises(ValueError):
            check_url(url, allow_private=True)

    def test_keeps_a_user_off_the_local_network(self):
        with pytest.raises(ValueError):
            check_url("http://192.168.1.10/hook", allow_private=False)

    def test_lets_an_admin_reach_the_local_network(self):
        check_url("http://192.168.1.10/hook", allow_private=True)

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com:abc/x",
            "https://example.com:99999/x",
            "https://example.com:0/x",
        ],
    )
    def test_refuses_a_port_that_isnt_one(self, url):
        with pytest.raises(ValueError, match="port"):
            check_url(url, allow_private=True)


def _serve(mocker, handler) -> None:
    mocker.patch.object(
        webhook,
        "_client",
        return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


_CONFIG = WebhookConfig(url="https://hooks.example.com/romm")


class TestSend:
    @pytest.fixture
    def respond(self, mocker):
        def install(status_code: int, text: str = ""):
            calls: list[httpx.Request] = []

            async def body():
                yield text.encode()

            # Streamed, as a response off the network is.
            def handler(request: httpx.Request) -> httpx.Response:
                calls.append(request)
                return httpx.Response(status_code, content=body())

            _serve(mocker, handler)
            return calls

        return install

    async def test_posts_the_built_request(self, respond):
        calls = respond(204)

        await send(_CONFIG, _message(), allow_private=False)

        [request] = calls
        assert str(request.url) == "https://hooks.example.com/romm"
        assert json.loads(request.content)["title"] == "Maintenance tonight"

    async def test_a_refusal_says_who_refused_and_why(self, respond):
        respond(404, '{"message": "Unknown Webhook"}')

        with pytest.raises(
            WebhookError, match="hooks.example.com answered 404: .*Unknown"
        ):
            await send(_CONFIG, _message(), allow_private=False)

    async def test_a_redirect_is_a_delivery_that_did_not_land(self, mocker):
        _serve(
            mocker,
            lambda request: httpx.Response(
                301, headers={"Location": "https://hooks.example.com/new"}
            ),
        )

        with pytest.raises(
            WebhookError,
            match="answered 301: redirected to https://hooks.example.com/new",
        ):
            await send(_CONFIG, _message(), allow_private=False)

    async def test_reads_only_the_start_of_an_endless_refusal(self, mocker):
        async def endless():
            while True:
                yield b"x" * 4096

        _serve(mocker, lambda request: httpx.Response(500, content=endless()))

        with pytest.raises(WebhookError) as caught:
            await send(_CONFIG, _message(), allow_private=False)

        assert str(caught.value) == (
            "hooks.example.com answered 500: " + "x" * webhook.ERROR_DETAIL_CHARS
        )

    async def test_gives_up_on_a_host_that_never_answers(self, mocker):
        async def handler(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(10)
            return httpx.Response(204)

        mocker.patch.object(webhook, "TIMEOUT_SECONDS", 0.05)
        _serve(mocker, handler)

        with pytest.raises(WebhookError, match="hooks.example.com did not answer"):
            await send(_CONFIG, _message(), allow_private=False)

    async def test_an_unreachable_host_is_a_webhook_error(self, mocker):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused")

        _serve(mocker, handler)

        with pytest.raises(WebhookError, match="Could not reach hooks.example.com"):
            await send(_CONFIG, _message(), allow_private=False)
