"""Redis failure injection shared by tests of multi-command writes."""

from typing import Any

from handler.redis_handler import async_cache


def fail_expire(mocker: Any) -> None:
    """Make EXPIRE raise, whether sent on its own or queued on a pipeline."""
    error = ConnectionError("valkey went away")
    mocker.patch.object(async_cache, "expire", side_effect=error)
    real_pipeline = async_cache.pipeline

    def pipeline(*args: Any, **kwargs: Any) -> Any:
        pipe = real_pipeline(*args, **kwargs)
        mocker.patch.object(pipe, "expire", side_effect=error)
        return pipe

    mocker.patch.object(async_cache, "pipeline", side_effect=pipeline)
