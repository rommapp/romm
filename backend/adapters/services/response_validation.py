from typing import Any, cast

from pydantic import ConfigDict, TypeAdapter, ValidationError

from logger.logger import log

# Undeclared keys pass through, and enum fields validate to the value sent.
_CONFIG = ConfigDict(extra="allow", use_enum_values=True)

# Tests set this so a cassette that drifts from its TypedDict fails the test.
RAISE_ON_MISMATCH = False

_adapters: dict[object, TypeAdapter[tuple[Any]]] = {}
_reported: set[tuple[str, frozenset[tuple[str, str]]]] = set()


class ResponseMismatchError(Exception):
    pass


def _adapter[T](tp: type[T]) -> TypeAdapter[tuple[T]]:
    # TypeAdapter refuses `config` for a bare TypedDict; inside a tuple the
    # config applies to it and to every TypedDict nested in it.
    if tp not in _adapters:
        _adapters[tp] = TypeAdapter(tuple[tp], config=_CONFIG)  # type: ignore[valid-type]
    return cast(TypeAdapter[tuple[T]], _adapters[tp])


def _path(loc: tuple[int | str, ...]) -> str:
    return ".".join("*" if isinstance(part, int) else part for part in loc) or "(root)"


def _first_difference(
    validated: object, raw: object, loc: tuple[int | str, ...] = ()
) -> tuple[int | str, ...] | None:
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
    if type(validated) is float and type(raw) is int:
        return None if validated == raw else loc
    return None if type(validated) is type(raw) and validated == raw else loc


def validate_response[T](tp: type[T], data: object, *, source: str) -> T:
    """Check a provider payload against its declared type and return it as sent.

    A value that fits only after coercion (a "1" for an int) is a mismatch. A
    mismatch is logged once per shape and the payload still returned, so a
    provider adding an enum value never costs a scan its metadata.

    Args:
        tp: The TypedDict (or container of one) the payload should match.
        data: The decoded JSON payload.
        source: Provider and endpoint, for the log line.
    """
    # Adapters return an empty payload on request errors; that is not drift.
    if not data:
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

    if (source, frozenset(problems)) not in _reported:
        _reported.add((source, frozenset(problems)))
        log.warning(
            "%s response does not match %r (%d problems): %s",
            source,
            tp,
            len(problems),
            details,
        )
    return cast(T, data)
