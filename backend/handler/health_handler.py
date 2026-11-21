"""Whether this API process is serving requests, for the readiness probe.

Each gunicorn worker holds its own flag. It reads nothing, so a probe costs
nothing and a dependency outage can't get RomM itself restarted.
"""

_ready = False


def mark_ready() -> None:
    global _ready
    _ready = True


def mark_not_ready() -> None:
    global _ready
    _ready = False


def is_ready() -> bool:
    return _ready
