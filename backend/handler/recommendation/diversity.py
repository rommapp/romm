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

# Neighbours allowed from any one series before the rest are dropped.
MAX_PER_SERIES: Final = 2

T = TypeVar("T")


def primary_series(rom: Rom) -> str | None:
    """The series a game belongs to, preferring the broader grouping.

    `franchises` is the umbrella ("Metroid") while `collections` is the
    narrower sub-series ("Metroid Prime"). The umbrella is the right diversity
    key: keying on collections let Super Metroid return two Metroid games plus
    two Metroid Prime games, which reads as four Metroids to anyone looking.
    """
    metadatum = rom.metadatum
    if metadatum is None:
        return None

    for values in (metadatum.franchises, metadatum.collections):
        if values:
            return str(values[0])

    return None


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

        series = primary_series(rom)
        if series is not None:
            if counts.get(series, 0) >= max_per_series:
                overflow.append((position, item))
                continue
            counts[series] = counts.get(series, 0) + 1

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
