"""Keeps a recommendation list from collapsing into one series.

Similarity ranking alone puts every Metroid game above every Metroidvania,
which makes "Similar games" a duplicate of a franchise filter. Someone who
owns Super Metroid already knows Metroid exists; the useful suggestion is
Castlevania.

Applied when serving rather than when building, so the policy can change
without rebuilding the index.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Final, TypeVar

from models.rom import Rom

# Neighbours allowed from any one series before the rest are dropped. Low
# enough that a deep franchise cannot fill the section on its own, high enough
# that a close same-series match is not traded away for a far weaker unrelated
# one: past the franchise, scores fall off a cliff.
MAX_PER_SERIES: Final = 3

T = TypeVar("T")


def series_keys(rom: Rom) -> set[str]:
    """Every series a game belongs to, franchises and collections alike.

    All of them, not just the first: IGDB lists a game's franchises in no
    stable order, so keying on one entry splits a single real series across
    several counters. Madden titles carry both "Madden" and "NFL", and the
    cap let four through -- two counted against each.
    """
    metadatum = rom.metadatum
    if metadatum is None:
        return set()

    return {
        str(value)
        for values in (metadatum.franchises, metadatum.collections)
        for value in (values or [])
        if value
    }


def primary_series(rom: Rom) -> str | None:
    """A single representative series, for display and attribution."""
    keys = series_keys(rom)
    return min(keys) if keys else None


def cap_by_series(
    items: Iterable[T],
    resolve_rom: Callable[[T], Rom | None],
    *,
    limit: int,
    max_per_series: int = MAX_PER_SERIES,
) -> list[T]:
    """Take items in order, allowing at most `max_per_series` from each series.

    Games with no series are never capped: they have nothing to cluster on, so
    treating them as one giant group would suppress most of an unmatched shelf.
    """
    # Positions are tracked so backfilled entries slot back into score order
    # rather than being appended after lower-scoring ones.
    selected: list[tuple[int, T]] = []
    overflow: list[tuple[int, T]] = []
    counts: dict[str, int] = {}

    for position, item in enumerate(items):
        rom = resolve_rom(item)
        if rom is None:
            continue

        keys = series_keys(rom)
        # Saturated on any one of its series is enough: a game sharing a
        # franchise with two already-picked entries is the repetition the cap
        # exists to stop, whichever of its franchises that happens to be.
        if keys and any(counts.get(key, 0) >= max_per_series for key in keys):
            overflow.append((position, item))
            continue

        for key in keys:
            counts[key] = counts.get(key, 0) + 1

        selected.append((position, item))
        if len(selected) >= limit:
            return [item for _, item in selected]

    # A shelf sitting deep in one franchise can cap away nearly everything,
    # leaving a section with two entries or none. A slightly repetitive row
    # beats an empty one, so the capped-out candidates backfill it.
    for entry in overflow:
        if len(selected) >= limit:
            break
        selected.append(entry)

    selected.sort(key=lambda entry: entry[0])
    return [item for _, item in selected]
