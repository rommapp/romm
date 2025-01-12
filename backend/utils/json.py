"""JSON-compatible module with sane defaults.

Inspiration taken from `python-engineio`.
https://github.com/miguelgrinberg/python-engineio/blob/main/src/engineio/json.py
"""

import datetime
import decimal
import json
import uuid
from json import *  # noqa: F401, F403
from json import dumps as __original_dumps
from typing import Any


class DefaultJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that supports encoding additional types."""

    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime.date, datetime.datetime, datetime.time)):
            return o.isoformat()
        if isinstance(o, (decimal.Decimal, uuid.UUID)):
            return str(o)
        return super().default(o)


def dumps(*args: Any, **kwargs: Any) -> str:  # type: ignore[no-redef]
    kwargs.setdefault("cls", DefaultJSONEncoder)
    return __original_dumps(*args, **kwargs)
