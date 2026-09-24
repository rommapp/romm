"""Webhook deliveries: RomM's own JSON, a Discord embed or an ntfy message."""

import asyncio
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import urlsplit, urlunsplit

import httpx

from config import has_proxy_env
from models.notification import NotificationLevel
from models.notification_channel import WebhookFormat
from utils.context import create_httpx_async_client
from utils.ssrf import validate_url_for_http_request
from utils.validation import ValidationError

from .config import WebhookConfig
from .messages import OutboundMessage

TIMEOUT_SECONDS: Final = 15
SIGNATURE_HEADER: Final = "X-RomM-Signature"
# How much of a refusal's body is read, for the error its owner sees.
ERROR_DETAIL_BYTES: Final = 1024
ERROR_DETAIL_CHARS: Final = 200

DISCORD_COLORS: Final[dict[str, int]] = {
    NotificationLevel.INFO: 0x3498DB,
    NotificationLevel.SUCCESS: 0x2ECC71,
    NotificationLevel.WARNING: 0xF1C40F,
    NotificationLevel.ERROR: 0xE74C3C,
}
NTFY_TAGS: Final[dict[str, str]] = {
    NotificationLevel.INFO: "information_source",
    NotificationLevel.SUCCESS: "white_check_mark",
    NotificationLevel.WARNING: "warning",
    NotificationLevel.ERROR: "rotating_light",
}
# ntfy's scale runs 1 to 5, where 3 is the default and 4 is high.
NTFY_ERROR_PRIORITY: Final = 4
NTFY_DEFAULT_PRIORITY: Final = 3


class WebhookError(RuntimeError):
    """The destination refused the delivery or could not be reached."""


@dataclass(frozen=True)
class WebhookRequest:
    url: str
    content: bytes
    headers: dict[str, str]


def split_ntfy_url(url: str) -> tuple[str, str]:
    """The server a topic URL points at and the topic, for ntfy's JSON publishing.

    Raises:
        ValueError: The URL names no topic.
    """
    parts = urlsplit(url)
    base_path, _, topic = parts.path.rstrip("/").rpartition("/")
    if not topic:
        raise ValueError(
            "An ntfy URL ends with its topic, such as https://ntfy.sh/romm"
        )
    return urlunsplit((parts.scheme, parts.netloc, base_path or "/", "", "")), topic


def check_url(url: str, format: WebhookFormat, allow_private: bool) -> None:
    """Refuse a webhook URL that can never be delivered to.

    Args:
        allow_private: Whether the channel may reach the local network, which
            only an admin's may.

    Raises:
        ValueError: With a reason fit to show the user.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("The URL must start with http:// or https://")
    try:
        port_ok = parts.port != 0
    except ValueError:
        port_ok = False
    if not port_ok:
        raise ValueError("The URL's port isn't valid")
    if not allow_private:
        try:
            validate_url_for_http_request(url)
        except ValidationError as exc:
            raise ValueError(exc.message) from exc
    if format == WebhookFormat.NTFY:
        split_ntfy_url(url)


def _json_payload(message: OutboundMessage) -> dict[str, Any]:
    n = message.notification
    return {
        "event": "notification",
        "id": n.id,
        "kind": n.kind,
        "level": n.level,
        "title": message.title,
        "body": message.body,
        "url": message.url,
        "data": n.data,
        "actor": {"id": n.actor.id, "username": n.actor.username} if n.actor else None,
        "created_at": n.created_at.isoformat(),
    }


def _discord_payload(message: OutboundMessage, channel_name: str) -> dict[str, Any]:
    n = message.notification
    embed: dict[str, Any] = {
        # Discord's own limits on an embed's title and description.
        "title": message.title[:256],
        "color": DISCORD_COLORS.get(n.level, DISCORD_COLORS[NotificationLevel.INFO]),
        "timestamp": n.created_at.isoformat(),
    }
    if message.body:
        embed["description"] = message.body[:4096]
    if message.url:
        embed["url"] = message.url
    footer = [channel_name, f"From {n.actor.username}" if n.actor else ""]
    embed["footer"] = {"text": " · ".join(part for part in footer if part)[:2048]}
    # A user's own text must not ping @everyone or a role.
    return {"username": "RomM", "embeds": [embed], "allowed_mentions": {"parse": []}}


def _ntfy_payload(message: OutboundMessage, topic: str) -> dict[str, Any]:
    n = message.notification
    payload: dict[str, Any] = {
        "topic": topic,
        "title": message.title,
        "message": message.body or message.title,
        "priority": (
            NTFY_ERROR_PRIORITY
            if n.level == NotificationLevel.ERROR
            else NTFY_DEFAULT_PRIORITY
        ),
        "tags": [NTFY_TAGS.get(n.level, NTFY_TAGS[NotificationLevel.INFO])],
    }
    if message.url:
        payload["click"] = message.url
    return payload


def build_request(
    config: WebhookConfig, message: OutboundMessage, channel_name: str = ""
) -> WebhookRequest:
    """The request a webhook gets for a message.

    Args:
        channel_name: What the owner called the channel, which a Discord embed
            shows in its footer.
    """
    # Identity, so a refusal's body is read as sent rather than decompressed.
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "RomM",
        "Accept-Encoding": "identity",
    }
    secret = config.get("secret")
    url = config["url"]

    match config["format"]:
        case WebhookFormat.DISCORD:
            payload = _discord_payload(message, channel_name)
        case WebhookFormat.NTFY:
            # JSON publishing takes non-ASCII titles that headers can't carry.
            url, topic = split_ntfy_url(url)
            payload = _ntfy_payload(message, topic)
            if secret:
                headers["Authorization"] = f"Bearer {secret}"
        case _:
            payload = _json_payload(message)

    content = json.dumps(payload).encode()
    if secret and config["format"] == WebhookFormat.JSON:
        digest = hmac.new(secret.encode(), content, hashlib.sha256).hexdigest()
        headers[SIGNATURE_HEADER] = f"sha256={digest}"
    return WebhookRequest(url=url, content=content, headers=headers)


def _client(allow_private: bool) -> httpx.AsyncClient:
    if allow_private:
        return httpx.AsyncClient(trust_env=has_proxy_env(), timeout=TIMEOUT_SECONDS)
    client = create_httpx_async_client()
    client.timeout = httpx.Timeout(TIMEOUT_SECONDS)
    return client


async def _error_detail(response: httpx.Response) -> str:
    body = b""
    async for chunk in response.aiter_raw():
        body += chunk
        if len(body) >= ERROR_DETAIL_BYTES:
            break
    text = body[:ERROR_DETAIL_BYTES].decode(response.encoding or "utf-8", "replace")
    return text.strip()[:ERROR_DETAIL_CHARS]


async def send(
    config: WebhookConfig,
    message: OutboundMessage,
    allow_private: bool,
    channel_name: str = "",
) -> None:
    """POST the message to the webhook, giving it TIMEOUT_SECONDS in all.

    Raises:
        WebhookError: The destination refused it, or could not be reached.
    """
    request = build_request(config, message, channel_name)
    host = urlsplit(request.url).hostname
    try:
        async with (
            asyncio.timeout(TIMEOUT_SECONDS),
            _client(allow_private) as client,
            client.stream(
                "POST", request.url, content=request.content, headers=request.headers
            ) as response,
        ):
            if not response.is_success:
                # Redirects aren't followed, so one is a delivery that didn't land.
                detail = (
                    f"redirected to {response.headers['location']}"
                    if response.is_redirect
                    else await _error_detail(response)
                )
                raise WebhookError(
                    f"{host} answered {response.status_code}"
                    + (f": {detail}" if detail else "")
                )
    except TimeoutError as exc:
        raise WebhookError(
            f"{host} did not answer within {TIMEOUT_SECONDS} seconds"
        ) from exc
    except ValidationError as exc:
        raise WebhookError(exc.message) from exc
    except httpx.HTTPError as exc:
        reason = str(exc) or type(exc).__name__
        raise WebhookError(f"Could not reach {host}: {reason}") from exc
