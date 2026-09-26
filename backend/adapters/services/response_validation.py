from typing import Any, cast

from pydantic import ConfigDict, TypeAdapter, ValidationError

from logger.logger import log

# Undeclared keys and enum values pass through as sent, so a matching payload
# comes back unchanged.
_CONFIG = ConfigDict(extra="allow", use_enum_values=True)

# Tests set this so a cassette that drifts from its TypedDict fails the test.
RAISE_ON_MISMATCH = False

_adapters: dict[object, TypeAdapter[tuple[Any]]] = {}
_reported: set[tuple[str, frozenset[tuple[str, str]]]] = set()


def _path(loc: tuple[int | str, ...]) -> str:
    # loc[0] is the index into the wrapping tuple.
    return ".".join("*" if isinstance(part, int) else part for part in loc[1:])


def _adapter[T](tp: type[T]) -> TypeAdapter[tuple[T]]:
    # TypeAdapter refuses `config` for a bare TypedDict; inside a tuple the
    # config applies to it and to every TypedDict nested in it.
    if tp not in _adapters:
        _adapters[tp] = TypeAdapter(tuple[tp], config=_CONFIG)  # type: ignore[valid-type]
    return cast(TypeAdapter[tuple[T]], _adapters[tp])


def validate_response[T](tp: type[T], data: object, *, source: str) -> T:
    """Check a provider payload against its declared type.

    A mismatch is logged once per shape and the raw payload returned, so a
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
        return _adapter(tp).validate_python((data,))[0]
    except ValidationError as exc:
        if RAISE_ON_MISMATCH:
            raise
        errors = exc.errors(include_url=False, include_input=False)
        signature = frozenset((_path(err["loc"]), err["type"]) for err in errors)
        if (source, signature) not in _reported:
            _reported.add((source, signature))
            details = "; ".join(
                f"{_path(err['loc'])}: {err['msg']}" for err in errors[:5]
            )
            log.warning(
                "%s response does not match %r (%d errors): %s",
                source,
                tp,
                exc.error_count(),
                details,
            )
        return cast(T, data)
