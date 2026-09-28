"""Redis stubs shared by tests of multi-command writes."""

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


def record_pipelines(mocker: Any) -> list[tuple[bool, list[str]]]:
    """Record whether each executed pipeline was a transaction, and its commands."""
    executed: list[tuple[bool, list[str]]] = []
    real_pipeline = async_cache.pipeline

    def pipeline(*args: Any, **kwargs: Any) -> Any:
        pipe = real_pipeline(*args, **kwargs)
        real_execute = pipe.execute

        async def execute(*args: Any, **kwargs: Any) -> Any:
            commands = [str(cmd[0]) for cmd, _ in pipe.command_stack]
            executed.append((pipe.is_transaction, commands))
            return await real_execute(*args, **kwargs)

        mocker.patch.object(pipe, "execute", side_effect=execute)
        return pipe

    mocker.patch.object(async_cache, "pipeline", side_effect=pipeline)
    return executed
