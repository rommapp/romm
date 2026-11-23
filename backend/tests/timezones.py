import os
import time
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def local_timezone(name: str) -> Iterator[None]:
    """Pin the process timezone that a naive datetime.timestamp() reads."""
    previous = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()
