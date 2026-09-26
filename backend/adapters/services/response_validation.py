from typing import Any, cast

from pydantic import ConfigDict, TypeAdapter, ValidationError

from logger.logger import log

# Undeclared keys pass through, and enum fields validate to the value sent.
_CONFIG = ConfigDict(extra="allow", use_enum_values=True)

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


def _first_difference(
    validated: object, raw: object, loc: tuple[int | str, ...] = ()
) -> tuple[int | str, ...] | None:
    # Pydantic hands back uncoerced scalars, and anything typed Any, as the same object.
    if validated is raw:
        return None
    if isinstance(validated, dict) and isinstance(raw, dict):
        for key, value in raw.items():
            found = _first_difference(validated.get(key), value, (*loc, key))
            if found is not None:
                return found
        return None
    if isinstance(validated, list) and isinstance(raw, list):
        for index, (left, right) in enumerate(zip(validated, raw, strict=True)):
            found = _first_difference(left, right, (*loc, index))
            if found is not None:
                return found
        return None
    # JSON writes a whole float as an integer, which typing accepts as a float.
    same_type = type(validated) is type(raw) or (
        type(validated) is float and type(raw) is int
    )
    return None if same_type and validated == raw else loc


def validate_response[T](tp: type[T], data: object, *, source: str) -> T:
    """Return a provider payload as sent, logging each new way it strays from `tp` once.

    Args:
        tp: The TypedDict (or container of one) the payload should match.
        data: The decoded JSON payload.
        source: Provider and endpoint, for the log line.
    """
    # Adapters return {} or [] on request errors; that is not drift.
    if data == {} or data == []:
        return cast(T, data)

    try:
        validated = _adapter(tp).validate_python((data,))[0]
    except ValidationError as exc:
        problems = [
            (_path(err["loc"][1:]), err["msg"])
            for err in exc.errors(include_url=False, include_input=False)
        ]
    else:
        loc = _first_difference(validated, data)
        if loc is None:
            return cast(T, data)
        problems = [(_path(loc), "matches only after coercion")]

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
    return cast(T, data)
