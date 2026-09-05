"""The HTTP transport to a container's broker.

urllib rather than an async client because every call here runs inside
`asyncio.to_thread`: the broker verbs block for as long as an emulator takes to
answer, and a save can legitimately hold one open for half a minute.

The bounded reads matter. urllib's `timeout` bounds a single socket operation,
not the transfer, so a broker feeding one byte per timeout window could hold a
read open indefinitely; reading in chunks against a wall clock is what ends it,
and the byte caps are what keep a misbehaving broker from filling memory.
"""

import json
import time
import urllib.error
import urllib.request
from email.message import Message
from typing import Any, NoReturn

from fastapi import HTTPException

from handler.streaming.config import ResolvedContainer
from logger.logger import log

# Broker HTTP deadlines, grouped by what the call actually waits on:
#   LAUNCH     - process spawn + config patch + window setup
#   LOAD_STATE - worst case 9 slot cycles x ~5s xdotool timeout
#   TRANSFER   - save archive and memory card transfers; state transfers use
#     their own per-emulator deadline, see capabilities.state_transfer_limits
#   CARD_HYDRATE / CARD_TEARDOWN - whole-card push at claim / pull at exit;
#     hydration may wait on a slow first-run card format, teardown must not
#     hold a closing session hostage for two minutes
LAUNCH_TIMEOUT = 10
LOAD_STATE_TIMEOUT = 60
TRANSFER_TIMEOUT = 60
# The broker waits for the core to report a running game before touching the
# tray, then sits out the tray settle, so this has to outlast that wait.
SWAP_DISC_TIMEOUT = 120
CARD_HYDRATE_TIMEOUT = 120
CARD_TEARDOWN_TIMEOUT = 30

# A pulled save archive can be large (PCSX2 ships whole 8 MB memory cards, a
# Wii NAND can hold many titles); 256 MB is generous for every emulator that
# separates its saves from its states.
SAVE_FILE_MAX_BYTES = 256 * 1024 * 1024

# Pull retries cover the window between the broker accepting a save and the
# emulator finishing the write (PINE/xdotool waits run up to ~15s per broker).
PULL_ATTEMPTS = 5
PULL_RETRY_DELAY = 3.0


def broker_url(container: ResolvedContainer, path: str) -> str:
    """
    Build the URL for the ROM broker API.

    The broker runs inside the emulator container on BROKER_PORT (default 8000).
    `broker_host` in config.yml is the host:port of the broker endpoint -
    separate from `host` which is the browser-facing stream URL.

    If broker_host is not set, we assume it is on the same host and swap the port.
    Example:
      host:         http://192.168.1.51:3000   (Selkies web UI, browser-facing)
      broker_host:  http://192.168.1.51:8000   (broker API, server-to-server)
    """
    broker_host = container.broker_host
    if not broker_host:
        # No usable broker host, raise a 502 with a clear cause so the
        # operator sees the misconfiguration instead of an opaque KeyError.
        raise HTTPException(
            status_code=502,
            detail=(
                "Streaming container has no usable broker_host/host. "
                "Set broker_host (or host with a scheme, e.g. http://...) "
                "in the streaming.containers config."
            ),
        )

    return f"{broker_host}{path}"


def broker_headers(container: ResolvedContainer) -> dict[str, str]:
    """Auth headers for a broker call, empty when no secret is configured.
    Returns a fresh dict so callers can add their own headers to it."""
    secret = container.broker_secret
    return {"X-Broker-Secret": secret} if secret else {}


# urllib's timeout bounds a single socket operation, not the transfer, so a
# broker feeding one byte per timeout window can hold a read open for as long
# as it likes. Reading in chunks against a wall clock is what ends it.
_BROKER_READ_CHUNK = 1024 * 1024
# Control responses are small; a JSON body past this is a broker fault.
_BROKER_JSON_MAX_BYTES = 4 * 1024 * 1024
# An error body only ever reaches a log line and a 502 detail.
_BROKER_ERROR_MAX_BYTES = 8 * 1024


def broker_error_body(exc: urllib.error.HTTPError) -> str:
    """The text a failed broker call answered with.

    HTTPError is itself the response, so it holds a connection until something
    closes it, and its body is as long as the broker cares to make it.
    """
    try:
        return exc.read(_BROKER_ERROR_MAX_BYTES).decode(errors="replace")
    except OSError as read_exc:
        log.warning("could not read broker error body, %s", read_exc)
        return ""
    finally:
        exc.close()


def _read_bounded(resp: Any, max_bytes: int, deadline: float) -> bytes:
    """Read up to `max_bytes` from an open response, giving up at `deadline`.

    Reads one byte past the cap so the caller can tell a body that fits from
    one that was truncated.
    """
    chunks: list[bytes] = []
    size = 0
    while size <= max_bytes:
        if time.monotonic() > deadline:
            raise TimeoutError("broker response exceeded its time budget")
        chunk = resp.read(min(_BROKER_READ_CHUNK, max_bytes + 1 - size))
        if not chunk:
            break
        chunks.append(chunk)
        size += len(chunk)
    return b"".join(chunks)


def request(
    container: ResolvedContainer,
    path: str,
    *,
    method: str = "POST",
    body: dict[str, Any] | None = None,
    timeout: float,
) -> Any:
    """
    Send a signed request to the broker and return its parsed JSON body (an
    empty dict when the broker replies with no content). Uses only Python
    stdlib urllib, no extra dependencies. Raises the underlying urllib/OS
    error; callers decide whether to surface or swallow it.
    """
    url = broker_url(container, path)
    headers = broker_headers(container)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(data))
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    deadline = time.monotonic() + timeout
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        raw = _read_bounded(resp, _BROKER_JSON_MAX_BYTES, deadline)
    if len(raw) > _BROKER_JSON_MAX_BYTES:
        raise ValueError("broker response exceeds size limit")
    return json.loads(raw) if raw else {}


def request_safe(
    container: ResolvedContainer,
    path: str,
    label: str,
    *,
    method: str = "POST",
    body: dict[str, Any] | None = None,
    timeout: float,
) -> Any | None:
    """
    Best-effort variant of request: returns the parsed body, or None if
    the broker is unreachable or errors. Never raises, control ops must not 500
    on a broker hiccup.
    """
    try:
        return request(container, path, method=method, body=body, timeout=timeout)
    except Exception as exc:
        log.warning("broker %s failed, %s", label, exc)
        # An HTTPError is an open response, and these routes are called often.
        if isinstance(exc, urllib.error.HTTPError):
            exc.close()
        return None


def get_binary(
    container: ResolvedContainer,
    path: str,
    *,
    max_bytes: int,
    timeout: float,
) -> tuple[Message, bytes]:
    """
    GET a binary body from the broker, returning (response headers, content).
    Headers come back because some routes carry metadata there. Raises the
    underlying urllib/OS error, or ValueError for an empty or oversized body.
    """
    req = urllib.request.Request(
        broker_url(container, path),
        method="GET",
        headers=broker_headers(container),
    )
    deadline = time.monotonic() + timeout
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        headers = resp.headers
        content = _read_bounded(resp, max_bytes, deadline)
    if not content:
        raise ValueError("broker returned an empty body")
    if len(content) > max_bytes:
        raise ValueError("broker response exceeds size limit")
    return headers, content


def get_binary_safe(
    container: ResolvedContainer,
    path: str,
    label: str,
    *,
    max_bytes: int,
    timeout: float,
) -> tuple[Message, bytes] | None:
    """
    Best-effort variant of get_binary: returns None instead of raising.
    A 404 is a normal answer on these routes (no state in the slot, no new
    saves, no captured frame), so it is not logged.
    """
    try:
        return get_binary(container, path, max_bytes=max_bytes, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # The error is a response too, and these routes are polled.
        exc.close()
        if exc.code != 404:
            log.warning("broker %s failed, HTTP %d", label, exc.code)
        return None
    except Exception as exc:
        log.warning("broker %s failed, %s", label, exc)
        return None


def put_binary_json(
    container: ResolvedContainer,
    path: str,
    content: bytes,
    label: str,
    *,
    content_type: str,
    timeout: float,
) -> dict[str, Any] | None:
    """
    PUT a binary body to the broker and return its parsed JSON reply, or None
    on failure. Best-effort, logs but never raises.
    """
    req = urllib.request.Request(
        broker_url(container, path),
        data=content,
        method="PUT",
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
            **broker_headers(container),
        },
    )
    deadline = time.monotonic() + timeout
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            body = json.loads(_read_bounded(resp, _BROKER_JSON_MAX_BYTES, deadline))
        return body if isinstance(body, dict) else {}
    except Exception as exc:
        log.warning("broker %s failed, %s", label, exc)
        if isinstance(exc, urllib.error.HTTPError):
            exc.close()
        return None


def put_binary(
    container: ResolvedContainer,
    path: str,
    content: bytes,
    label: str,
    *,
    content_type: str,
    timeout: float,
) -> bool:
    """PUT a binary body to the broker, reporting whether it acked with ok."""
    body = put_binary_json(
        container, path, content, label, content_type=content_type, timeout=timeout
    )
    return bool(body and body.get("status") == "ok")


def raise_http_error(exc: urllib.error.HTTPError) -> NoReturn:
    """Translate a broker error response into the 502 the frontend parses."""
    error_body = broker_error_body(exc)
    log.error("broker HTTP error %d: %s", exc.code, error_body)
    try:
        detail = json.loads(error_body)
    except Exception:
        detail = error_body
    raise HTTPException(
        status_code=502, detail=f"Broker returned {exc.code}: {detail}"
    ) from exc


def raise_unreachable(
    exc: BaseException, subject: str, url: str, hint: str
) -> NoReturn:
    """Translate a transport failure into a 503 naming what to check."""
    log.error("broker unreachable at %s: %s", url, exc)
    raise HTTPException(
        status_code=503, detail=f"Could not reach {subject} at {url}. {hint}"
    ) from exc
