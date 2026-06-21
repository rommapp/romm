"""Redis-backed state, codes, and rate limits for the device authorization flow.

RFC 8628-style: a client polls a token endpoint while the user approves the
pairing out-of-band through the web UI. State lives entirely in Redis; nothing
about a pending request touches the database until the user approves.
"""

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Final

from fastapi import HTTPException, Request, status
from yarl import URL

from handler.redis_handler import sync_cache
from utils.client_tokens import PAIR_ALPHABET

DEVICE_CODE_BYTES: Final[int] = 32  # -> 64 hex chars
USER_CODE_LENGTH: Final[int] = 8

PENDING_TTL_SECONDS: Final[int] = 600  # 10-minute hard ceiling
DENIED_TTL_SECONDS: Final[int] = 60  # shrink window after explicit deny
POLL_DEFAULT_INTERVAL_SECONDS: Final[int] = 5

AUTHORIZE_RATE_LIMIT: Final[int] = 10
TOKEN_POLL_RATE_LIMIT: Final[int] = 60
RATE_LIMIT_WINDOW_SECONDS: Final[int] = 60

_KEY_DC = "device_auth:dc:{}"
_KEY_UC = "device_auth:uc:{}"
_KEY_POLL_LAST = "device_auth:poll_last:{}"
_KEY_AUTHORIZE_RATE = "device_auth:rate:authorize:{}"
_KEY_TOKEN_RATE = (
    "device_auth:rate:token:{}"  # nosec B105 -- redis key template, not a secret
)


class FlowStatus:
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


def normalize_user_code(code: str) -> str:
    """Strip separators and uppercase a user-typed pairing code."""
    return code.replace("-", "").replace(" ", "").upper()


def generate_device_code() -> str:
    return secrets.token_hex(DEVICE_CODE_BYTES)


def generate_user_code() -> str:
    return "".join(secrets.choice(PAIR_ALPHABET) for _ in range(USER_CODE_LENGTH))


def build_verification_paths(user_code: str) -> tuple[str, str]:
    """Return the web-UI approval paths.

    Only a fixed relative path is returned; the client joins it with the origin
    it was configured to reach, so the server stays origin-agnostic (in
    development the web UI and API run on different ports). The path is a server
    constant and never incorporates client input.
    """
    verification_path = "/pair/device"
    verification_path_complete = str(
        URL(verification_path).with_query(user_code=user_code)
    )
    return verification_path, verification_path_complete


def check_authorize_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    key = _KEY_AUTHORIZE_RATE.format(client_ip)
    count = sync_cache.incr(key)

    # Set the TTL only when the counter is first created so the window actually resets
    if count == 1:
        sync_cache.expire(key, RATE_LIMIT_WINDOW_SECONDS)

    if count > AUTHORIZE_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authorize attempts. Try again later.",
        )


def check_token_poll_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    key = _KEY_TOKEN_RATE.format(client_ip)
    count = sync_cache.incr(key)

    # Set the TTL only when the counter is first created so the polling window actually resets
    if count == 1:
        sync_cache.expire(key, RATE_LIMIT_WINDOW_SECONDS)

    if count > TOKEN_POLL_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many polling attempts. Try again later.",
        )


def polled_too_fast(device_code: str, interval_seconds: int) -> bool:
    """Per-device_code poll pacing check.

    Records the wall-clock ms of this call and returns True if the caller
    polled inside ``interval_seconds`` of the previous poll.
    """
    key = _KEY_POLL_LAST.format(device_code)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    prev_raw = sync_cache.getset(key, str(now_ms))
    sync_cache.expire(key, max(interval_seconds * 4, 30))
    if prev_raw is None:
        return False
    try:
        prev_ms = int(prev_raw.decode() if isinstance(prev_raw, bytes) else prev_raw)
    except (ValueError, AttributeError):
        return False
    return (now_ms - prev_ms) < (interval_seconds * 1000)


def store_pending(device_code: str, user_code: str, data: dict[str, Any]) -> None:
    payload = {
        **data,
        "status": FlowStatus.PENDING,
        "user_code": user_code,
    }
    sync_cache.setex(
        _KEY_DC.format(device_code),
        PENDING_TTL_SECONDS,
        json.dumps(payload),
    )
    sync_cache.setex(
        _KEY_UC.format(user_code),
        PENDING_TTL_SECONDS,
        device_code,
    )


def load_pending(device_code: str) -> dict[str, Any] | None:
    raw = sync_cache.get(_KEY_DC.format(device_code))
    if not raw:
        return None
    return json.loads(raw)


def resolve_device_code_from_user_code(user_code: str) -> str | None:
    raw = sync_cache.get(_KEY_UC.format(user_code))
    if not raw:
        return None
    return raw.decode() if isinstance(raw, bytes) else raw


def pending_expires_at(device_code: str) -> datetime:
    """Derive a pending request's deadline from the current Redis TTL."""
    remaining = sync_cache.ttl(_KEY_DC.format(device_code))
    if remaining is None or remaining < 0:
        remaining = 0
    return datetime.now(timezone.utc) + timedelta(seconds=int(remaining))


def mark_approved(
    device_code: str,
    *,
    raw_token: str,
    device_id: str,
    scopes: list[str],
    expires_at: datetime | None,
) -> None:
    pending = load_pending(device_code)
    if pending is None:
        return
    user_code = pending.get("user_code")
    approved = {
        "status": FlowStatus.APPROVED,
        "raw_token": raw_token,
        "device_id": device_id,
        "scopes": scopes,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    remaining = sync_cache.ttl(_KEY_DC.format(device_code))
    if remaining is None or remaining < 1:
        remaining = PENDING_TTL_SECONDS
    sync_cache.setex(
        _KEY_DC.format(device_code),
        min(remaining, PENDING_TTL_SECONDS),
        json.dumps(approved),
    )
    if user_code:
        sync_cache.delete(_KEY_UC.format(user_code))


def mark_denied(device_code: str) -> None:
    pending = load_pending(device_code)
    if pending is None:
        return
    user_code = pending.get("user_code")
    denied = {"status": FlowStatus.DENIED}
    sync_cache.setex(
        _KEY_DC.format(device_code),
        DENIED_TTL_SECONDS,
        json.dumps(denied),
    )
    if user_code:
        sync_cache.delete(_KEY_UC.format(user_code))


def consume_approved(device_code: str) -> dict[str, Any] | None:
    """One-shot read of an approved blob. Deletes the key on success.

    Callers MUST have already established via ``load_pending`` that the status
    is approved; this helper is defensive and will refuse to return a non-
    approved payload (and will reinsert it so a subsequent flow can proceed).
    """
    raw = sync_cache.getdel(_KEY_DC.format(device_code))
    if not raw:
        return None
    data = json.loads(raw)
    if data.get("status") != FlowStatus.APPROVED:
        sync_cache.setex(
            _KEY_DC.format(device_code),
            PENDING_TTL_SECONDS,
            json.dumps(data),
        )
        return None
    return data
