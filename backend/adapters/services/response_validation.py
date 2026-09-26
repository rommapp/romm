import json
from typing import Any, cast

from pydantic import ConfigDict, TypeAdapter, ValidationError

from logger.logger import log

# Strict JSON mode takes each value only as its declared type, while enum values
# and whole numbers for floats still pass as JSON sends them.
_CONFIG = ConfigDict(extra="allow", use_enum_values=True, strict=True)

# Tests set this so a cassette that drifts from its TypedDict fails the test.
RAISE_ON_MISMATCH = False

_adapters: dict[object, TypeAdapter[tuple[Any]]] = {}
_reported: set[tuple[str, tuple[str, str]]] = set()


# A BaseException, so a handler's `except Exception` cannot hide drift from a test.
class ResponseMismatchError(BaseException):
    pass


def _adapter(tp: object) -> TypeAdapter[tuple[Any]]:
    # TypeAdapter refuses `config` for a bare TypedDict; inside a tuple the
    # config applies to it and to every TypedDict nested in it.
    if tp not in _adapters:
        _adapters[tp] = TypeAdapter(tuple[tp], config=_CONFIG)  # type: ignore[valid-type]
    return _adapters[tp]


def _path(loc: tuple[int | str, ...]) -> str:
    # List indices and id-keyed dict entries (RA achievements) share one shape.
    return (
        ".".join(
            "*" if isinstance(part, int) or part.isdigit() else part for part in loc
        )
        or "(root)"
    )


def parse_response[T](tp: type[T], body: str | bytes, *, source: str) -> T | None:
    """Decode a provider reply, logging each new way it strays from `tp` once.

    Args:
        tp: The TypedDict (or container of one) the reply should match.
        body: The raw JSON reply.
        source: Provider and endpoint, for the log line.

    Returns:
        The decoded reply, as sent even when it strays from `tp`, or None when
        its top level is not the declared JSON type at all.

    Raises:
        json.JSONDecodeError: The body is not JSON at all.
    """
    raw = body.encode() if isinstance(body, str) else body
    try:
        return cast(T, _adapter(tp).validate_json(b"[" + raw + b"]")[0])
    except ValidationError as exc:
        errors = exc.errors(include_url=False, include_input=False)

    # A mismatch still hands back the reply as sent; invalid JSON raises here.
    data = json.loads(raw)
    problems = [(_path(err["loc"][1:]), err["msg"]) for err in errors]
    details = "; ".join(f"{path}: {msg}" for path, msg in problems[:5])
    if RAISE_ON_MISMATCH:
        raise ResponseMismatchError(
            f"{source} response does not match {tp!r}: {details}"
        )

    unreported = {(source, problem) for problem in problems} - _reported
    if unreported:
        _reported.update(unreported)
        log.warning(
            "%s response does not match %r (%d problems): %s",
            source,
            tp,
            len(problems),
            details,
        )
    if any(len(err["loc"]) == 1 for err in errors):
        return None
    return cast(T, data)
