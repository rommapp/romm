"""Webhook deliveries: RomM's own JSON, signed when the channel has a secret."""

import asyncio
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import urlsplit

import httpx

from config import has_proxy_env
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


class WebhookError(RuntimeError):
    """The destination refused the delivery or could not be reached."""


@dataclass(frozen=True)
class WebhookRequest:
    url: str
    content: bytes
    headers: dict[str, str]


def check_url(url: str, allow_private: bool) -> None:
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


def build_request(config: WebhookConfig, message: OutboundMessage) -> WebhookRequest:
    """The request a webhook gets for a message."""
    # Identity, so a refusal's body is read as sent rather than decompressed.
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "RomM",
        "Accept-Encoding": "identity",
    }
    content = json.dumps(_json_payload(message)).encode()
    secret = config.get("secret")
    if secret:
        digest = hmac.new(secret.encode(), content, hashlib.sha256).hexdigest()
        headers[SIGNATURE_HEADER] = f"sha256={digest}"
    return WebhookRequest(url=config["url"], content=content, headers=headers)


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
    config: WebhookConfig, message: OutboundMessage, allow_private: bool
) -> None:
    """POST the message to the webhook, giving it TIMEOUT_SECONDS in all.

    Raises:
        WebhookError: The destination refused it, or could not be reached.
    """
    request = build_request(config, message)
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
