import logging
import re
from typing import Final

# Redis keys shared between the logging handler (producer, runs in every
# process), the forwarder (relays pub/sub to Socket.IO) and the REST backfill
# endpoint.
LOG_CHANNEL: Final = "romm:logs"
LOG_BUFFER_KEY: Final = "romm:logs:buffer"
LOG_BUFFER_SIZE: Final = 1000

# Strips ANSI SGR escapes (colors) that the `highlight()` helper embeds in log
# messages — they render as colors on a terminal but as garbage in a browser.
_ANSI_RE: Final = re.compile(r"\x1b\[[0-9;]*m")


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

    def __init__(self) -> None:
        super().__init__()
        # The redaction regex lives in handler.metadata.base_handler, which
        # pulls a heavy import chain (and, during early boot, a partially
        # initialized handler.redis_handler). Resolve it lazily and cache it
        # once available; until then, skip redaction — exactly like the
        # Formatter does for the first few boot lines.
        self._redactor: re.Pattern[str] | None = None

    def _redact(self, message: str) -> str:
        if self._redactor is None:
            try:
                from handler.metadata.base_handler import SENSITIVE_KEYS_REGEX

                self._redactor = SENSITIVE_KEYS_REGEX
            except Exception:  # noqa: BLE001 - not importable yet during boot
                return message
        return self._redactor.sub(r"\1=***", message)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from handler.redis_handler import redis_client
            from utils import json_module

            module = getattr(record, "module_name", record.module)
            payload = json_module.dumps(
                {
                    "ts": int(record.created * 1000),
                    "level": record.levelname,
                    "module": str(module).lower(),
                    "message": self._redact(_ANSI_RE.sub("", record.getMessage())),
                }
            )

            # A single pipeline keeps buffer write + publish to one round-trip.
            pipe = redis_client.pipeline()
            pipe.lpush(LOG_BUFFER_KEY, payload)
            pipe.ltrim(LOG_BUFFER_KEY, 0, LOG_BUFFER_SIZE - 1)
            pipe.publish(LOG_CHANNEL, payload)
            pipe.execute()
        except Exception:  # noqa: BLE001 - best-effort mirror; never raise/spam
            pass
