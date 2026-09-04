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
    pipe = sync_cache.pipeline()
    pipe.incr(key)
    # NX in the same transaction as the INCR: only the call that starts a window
    # sets its TTL, and no counter can be left without one.
    pipe.expire(key, window_seconds, nx=True)
    count, _ = pipe.execute()

    if count > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
        )
