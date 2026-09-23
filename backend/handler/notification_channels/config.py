"""What a channel keeps sealed: where it sends, and how."""

from typing import Any, NotRequired, TypedDict
from urllib.parse import urlsplit

from utils.secret_box import UnsealError, seal, unseal


class WebhookConfig(TypedDict):
    url: str
    format: str
    # The HMAC key of a JSON webhook, or the access token of an ntfy topic.
    secret: NotRequired[str | None]


class EmailConfig(TypedDict):
    address: str


def seal_config(config: WebhookConfig | EmailConfig) -> str:
    return seal(dict(config))


def read_config(sealed: str) -> dict[str, Any]:
    """A channel's config; empty when the auth secret changed since it was saved."""
    try:
        return unseal(sealed)
    except UnsealError:
        return {}


def origin(url: str) -> str:
    """The URL's scheme, host and port: whom a request to it reaches."""
    parts = urlsplit(url)
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname or ''}{port}"


def masked_url(url: str) -> str:
    """The URL with its path hidden, which is where a webhook keeps its token."""
    tail = urlsplit(url).path.rstrip("/")[-4:]
    return f"{origin(url)}/…{tail}" if tail else origin(url)
