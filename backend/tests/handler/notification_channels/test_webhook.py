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
    split_ntfy_url,
)
from models.notification import NotificationLevel
from models.notification_channel import WebhookFormat

from .fixtures import make_actor, make_notification


def _message(**overrides) -> OutboundMessage:
    return OutboundMessage(
        notification=make_notification(**overrides),
        title="Maintenance tonight",
        body="RomM restarts at 23:00",
        url="https://romm.example.com/platforms",
    )


class TestJsonFormat:
    def test_carries_the_notification_and_its_text(self):
        request = build_request(
            WebhookConfig(url="https://hooks.example.com/romm", format="json"),
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
            WebhookConfig(url="https://hooks.example.com", format="json", secret="k"),
            _message(),
        )

        expected = hmac.new(b"k", request.content, hashlib.sha256).hexdigest()
        assert request.headers[webhook.SIGNATURE_HEADER] == f"sha256={expected}"


class TestDiscordFormat:
    def test_sends_an_embed_that_pings_nobody(self):
        request = build_request(
            WebhookConfig(url="https://discord.com/api/webhooks/1/t", format="discord"),
            _message(level=NotificationLevel.ERROR, actor=make_actor()),
            "#romm",
        )

        payload = json.loads(request.content)
        [embed] = payload["embeds"]
        assert embed["title"] == "Maintenance tonight"
        assert embed["description"] == "RomM restarts at 23:00"
        assert embed["url"] == "https://romm.example.com/platforms"
        assert embed["color"] == webhook.DISCORD_COLORS[NotificationLevel.ERROR]
        assert embed["footer"] == {"text": "#romm · From admin"}
        assert payload["allowed_mentions"] == {"parse": []}

    def test_names_the_channel_alone_without_a_sender(self):
        request = build_request(
            WebhookConfig(url="https://discord.com/api/webhooks/1/t", format="discord"),
            _message(),
            "#romm",
        )

        [embed] = json.loads(request.content)["embeds"]
        assert embed["footer"] == {"text": "#romm"}

    def test_keeps_within_discords_limits(self):
        message = OutboundMessage(
            notification=make_notification(),
            title="t" * 300,
            body="b" * 5000,
            url=None,
        )

        [embed] = json.loads(
            build_request(
                WebhookConfig(
                    url="https://discord.com/api/webhooks/1/t", format="discord"
                ),
                message,
            ).content
        )["embeds"]

        assert (len(embed["title"]), len(embed["description"])) == (256, 4096)
        assert "url" not in embed


class TestNtfyFormat:
    def test_publishes_json_to_the_server_with_the_topic(self):
        request = build_request(
            WebhookConfig(
                url="https://ntfy.example.com/sub/romm", format="ntfy", secret="tk_1"
            ),
            _message(level=NotificationLevel.ERROR),
        )

        payload = json.loads(request.content)
        assert request.url == "https://ntfy.example.com/sub"
        assert payload["topic"] == "romm"
        assert payload["message"] == "RomM restarts at 23:00"
        assert payload["priority"] == webhook.NTFY_ERROR_PRIORITY
        assert payload["click"] == "https://romm.example.com/platforms"
        assert request.headers["Authorization"] == "Bearer tk_1"
        assert webhook.SIGNATURE_HEADER not in request.headers

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://ntfy.sh/romm", ("https://ntfy.sh/", "romm")),
            ("https://host/ntfy/romm/", ("https://host/ntfy", "romm")),
        ],
    )
    def test_splits_a_topic_url(self, url, expected):
        assert split_ntfy_url(url) == expected

    def test_a_url_without_a_topic_is_refused(self):
        with pytest.raises(ValueError, match="topic"):
            split_ntfy_url("https://ntfy.sh/")


class TestCheckUrl:
    @pytest.mark.parametrize("url", ["ftp://example.com/x", "not a url", "https://"])
    def test_refuses_anything_but_http(self, url):
        with pytest.raises(ValueError):
            check_url(url, WebhookFormat.JSON, allow_private=True)

    def test_keeps_a_user_off_the_local_network(self):
        with pytest.raises(ValueError):
            check_url(
                "http://192.168.1.10/hook", WebhookFormat.JSON, allow_private=False
            )

    def test_lets_an_admin_reach_the_local_network(self):
        check_url("http://192.168.1.10/hook", WebhookFormat.JSON, allow_private=True)

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
            check_url(url, WebhookFormat.JSON, allow_private=True)


def _serve(mocker, handler) -> None:
    mocker.patch.object(
        webhook,
        "_client",
        return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


_CONFIG = WebhookConfig(url="https://hooks.example.com/romm", format="json")


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

        with pytest.raises(WebhookError, match="discord.com answered 404: .*Unknown"):
            await send(
                WebhookConfig(
                    url="https://discord.com/api/webhooks/1/t", format="discord"
                ),
                _message(),
                allow_private=False,
            )

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
