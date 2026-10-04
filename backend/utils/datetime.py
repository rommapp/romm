from collections.abc import Sequence
from datetime import datetime, timezone


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_utc_timestamp(
    value: str | None, formats: Sequence[str] = (), *, iso: bool = False
) -> int | None:
    """Seconds since the epoch for a date string, reading one without an offset as UTC.

    Args:
        value: The date as the provider sent it.
        formats: strptime formats to try, in order.
        iso: Try ISO 8601 (including a trailing "Z") before `formats`.

    Returns:
        The timestamp, or None when nothing matches.
    """
    if not value:
        return None

    if iso:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError, AttributeError):
            pass
        else:
            return int(to_utc(parsed).timestamp())

    for fmt in formats:
        try:
            # to_utc keeps an offset parsed by %z and pins any other date to UTC.
            parsed = datetime.strptime(value, fmt)  # noqa: DTZ007
        except (TypeError, ValueError):
            continue
        return int(to_utc(parsed).timestamp())

    return None


def format_utc(timestamp_ms: float, fmt: str) -> str:
    """Format a millisecond timestamp as its UTC date and time."""
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime(fmt)
