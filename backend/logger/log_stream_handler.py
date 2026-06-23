import logging
from typing import Final

from logger.formatter import redact_sensitive, resolve_module_name, strip_ansi

# Redis keys shared between the logging handler (producer, runs in every
# process), the forwarder (relays pub/sub to Socket.IO) and the REST backfill
# endpoint.
LOG_CHANNEL: Final = "romm:logs"
LOG_BUFFER_KEY: Final = "romm:logs:buffer"
LOG_BUFFER_SIZE: Final = 1000


class LogStreamHandler(logging.Handler):
    """Logging handler that mirrors records to Redis for real-time streaming.

    Each record is serialized to a small JSON payload, appended to a capped
    Redis ring buffer (for backfill on view open) and published to a pub/sub
    channel that a single forwarder in the main app relays to admin Socket.IO
    clients.

    The handler is attached to the ``romm`` logger, so it runs in every process
    that imports it (main app, RQ workers, scheduler, watchers) and the stream
    covers the whole backend.

    Failures are swallowed **silently** — stdout is the source-of-truth log, so
    a Redis hiccup (or the metadata package not being importable yet during the
    first few boot lines) must neither raise into the app nor spam tracebacks
    via ``handleError``.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from handler.redis_handler import redis_client
            from utils import json_module

            module = resolve_module_name(record)
            payload = json_module.dumps(
                {
                    "ts": int(record.created * 1000),
                    "level": record.levelname,
                    "module": module.lower(),
                    "message": redact_sensitive(strip_ansi(record.getMessage())),
                }
            )

            # A single pipeline keeps buffer write + publish to one round-trip.
            pipe = redis_client.pipeline()
            pipe.lpush(LOG_BUFFER_KEY, payload)
            pipe.ltrim(LOG_BUFFER_KEY, 0, LOG_BUFFER_SIZE - 1)
            pipe.publish(LOG_CHANNEL, payload)
            pipe.execute()
        except Exception:  # noqa: BLE001 - never raise/spam  # nosec B110
            pass
