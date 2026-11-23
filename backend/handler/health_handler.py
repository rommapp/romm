"""Whether this gunicorn worker serves requests, held in memory so a probe reads nothing."""

_ready = False


def mark_ready() -> None:
    global _ready
    _ready = True


def mark_not_ready() -> None:
    global _ready
    _ready = False


def is_ready() -> bool:
    return _ready
