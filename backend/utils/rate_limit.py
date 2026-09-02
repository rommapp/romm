"""Fixed-window, Redis-backed request rate limiting."""

from fastapi import HTTPException, Request, status

from handler.redis_handler import sync_cache


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(
    key: str, *, max_requests: int, window_seconds: int, detail: str
) -> None:
    """Count one call against a fixed window, raising 429 once the cap is passed.

    Args:
        key: Redis key the window is counted under, already scoped to whatever
            identifies the caller (usually their IP).
        max_requests: Calls allowed per window.
        window_seconds: Window length.
        detail: Message returned with the 429.
    """
    count = sync_cache.incr(key)

    # Set the TTL only when the counter is first created so the window actually resets
    if count == 1:
        sync_cache.expire(key, window_seconds)

    if count > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
        )
