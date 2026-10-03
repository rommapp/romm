"""Minimum player age from the age ratings providers and admins record on a ROM."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Final

# The ROM columns `compute_min_age` reads, so writers know when to recompute it.
MIN_AGE_SOURCE_COLUMNS: Final = (
    "manual_metadata",
    "igdb_metadata",
    "ss_metadata",
    "launchbox_metadata",
    "steam_metadata",
)

# Boards whose ratings are already ages (with an `L` or `ALL` meaning any age).
_NUMERIC_BOARDS: Final = frozenset(
    {"PEGI", "USK", "GRAC", "CLASS_IND", "SS", "ELSPA", "JV"}
)

_LETTER_AGES: Final[dict[str, dict[str, int]]] = {
    # E is the pre-1998 "Kids to Adults" (KA) floor of six.
    "ESRB": {"EC": 3, "E": 6, "KA": 6, "E10": 10, "T": 13, "M": 17, "AO": 18},
    "CERO": {"A": 0, "B": 12, "C": 15, "D": 17, "Z": 18},
    "ACB": {"G": 0, "PG": 8, "M": 15, "MA15": 15, "R18": 18, "X18": 18, "RC": 18},
    "BBFC": {"U": 0, "PG": 8, "12": 12, "12A": 12, "15": 15, "18": 18, "R18": 18},
}

_BOARD_ALIASES: Final = {
    # Brazil's board was DJCTQ before ClassInd; Australia's was the OFLC.
    "DJCTQ": "CLASS_IND",
    "CLASSIND": "CLASS_IND",
    "OFLC": "ACB",
}

_ANY_AGE: Final = frozenset({"L", "ALL"})
_DIGITS: Final = re.compile(r"\d+")


def rating_min_age(board: str, rating: str) -> int | None:
    """The youngest age `rating` from `board` admits, or None when unknown."""
    board = board.split("(")[0].strip().upper().replace(" ", "_")
    board = _BOARD_ALIASES.get(board, board)
    # LaunchBox spells Kids to Adults "K-A".
    code = rating.upper().replace(" ", "").replace("+", "").replace("-", "")
    if not code:
        return None
    if board in _LETTER_AGES:
        return _LETTER_AGES[board].get(code)
    if board in _NUMERIC_BOARDS:
        if code in _ANY_AGE:
            return 0
        digits = _DIGITS.search(code)
        return int(digits.group()) if digits else None
    return None


def compute_min_age(metadata: Mapping[str, Any]) -> int | None:
    """Precompute `Rom.min_age`, the strictest age any known rating sets, where a
    manual rating list replaces the providers' ratings as it does on display.

    Args:
        metadata: Each `MIN_AGE_SOURCE_COLUMNS` column's value, by column name.
    """
    manual = _blob(metadata, "manual_metadata").get("age_ratings")
    if manual is not None:
        return max(_manual_ages(manual), default=None)
    return max(_provider_ages(metadata), default=None)


def _blob(metadata: Mapping[str, Any], column: str) -> Mapping[str, Any]:
    value = metadata.get(column)
    return value if isinstance(value, Mapping) else {}


def _known_ages(ratings: Iterable[tuple[str, str]]) -> Iterator[int]:
    for board, rating in ratings:
        if (age := rating_min_age(board, rating)) is not None:
            yield age


def _manual_ages(entries: Any) -> Iterator[int]:
    if isinstance(entries, str):
        entries = [entries]
    if not isinstance(entries, list):
        return
    for entry in entries:
        if isinstance(entry, str) and ":" in entry:
            board, _, rating = entry.partition(":")
            if (age := rating_min_age(board, rating)) is not None:
                yield age


def _provider_ages(metadata: Mapping[str, Any]) -> Iterator[int]:
    for column in ("igdb_metadata", "ss_metadata"):
        entries = _blob(metadata, column).get("age_ratings")
        if not isinstance(entries, list):
            continue
        yield from _known_ages(
            (str(entry.get("category") or ""), str(entry.get("rating") or ""))
            for entry in entries
            if isinstance(entry, Mapping)
        )
    esrb = _blob(metadata, "launchbox_metadata").get("esrb")
    if isinstance(esrb, str):
        yield from _known_ages([("ESRB", esrb)])
    steam_age = _blob(metadata, "steam_metadata").get("required_age")
    if isinstance(steam_age, int) and steam_age > 0:
        yield steam_age
