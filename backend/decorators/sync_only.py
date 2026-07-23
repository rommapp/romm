from fastapi import HTTPException, status

import config


def sync_only_route_disabled() -> None:
    """FastAPI dependency that hides ROM-file-centric routes in sync-only mode.

    Reads the flag at request time (not import time) so tests can toggle it.
    Raises 404 rather than 403 so gated routes are indistinguishable from
    nonexistent ones.
    """
    if config.SYNC_ONLY_MODE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not available in sync-only mode",
        )
