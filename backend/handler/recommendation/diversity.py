"""Keeps a recommendation list from collapsing into one series.

Similarity ranking alone puts every Metroid game above every Metroidvania,
which makes "Similar games" a duplicate of a franchise filter. Applied when
serving rather than when building, so the policy can change without a rebuild.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Final, TypeVar

from models.rom import Rom

# Neighbours allowed from any one series before the rest are dropped. Low
# enough that a deep franchise cannot fill the section on its own, high enough
# that a close same-series match is not traded for a far weaker unrelated one.
MAX_PER_SERIES: Final = 3

# Entries to rank per entry returned, since the caps below drop candidates.
OVERFETCH_FACTOR: Final = 5

T = TypeVar("T")


def series_keys(rom: Rom) -> set[str]:
    """Every series a game belongs to, franchises and collections alike.

    All of them, not just the first: IGDB lists franchises in no stable order,
    so keying on one splits a single real series across several counters.
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


def cap_by_series(
    items: Iterable[T],
    resolve_rom: Callable[[T], Rom | None],
    *,
    limit: int,
    max_per_series: int = MAX_PER_SERIES,
    max_per_platform: int | None = None,
) -> list[T]:
    """Take items in order, allowing at most `max_per_series` from each series.

    Games with no series are never capped: treating them as one group would
    suppress most of an unmatched shelf. `max_per_platform` additionally stops
    one platform owning the result, which only the personalised feed wants.
    """
    # Positions are tracked so backfilled entries slot back into score order
    # rather than being appended after lower-scoring ones.
    selected: list[tuple[int, T]] = []
    overflow: list[tuple[int, T]] = []
    counts: dict[str, int] = {}
    platform_counts: dict[int, int] = {}

    for position, item in enumerate(items):
        rom = resolve_rom(item)
        if rom is None:
            continue

        keys = series_keys(rom)
        # Saturated on any one of its series is enough: whichever franchise it
        # is, a third entry from it is the repetition the cap exists to stop.
        if keys and any(counts.get(key, 0) >= max_per_series for key in keys):
            overflow.append((position, item))
            continue

        if (
            max_per_platform is not None
            and platform_counts.get(rom.platform_id, 0) >= max_per_platform
        ):
            overflow.append((position, item))
            continue

        for key in keys:
            counts[key] = counts.get(key, 0) + 1
        platform_counts[rom.platform_id] = platform_counts.get(rom.platform_id, 0) + 1

        selected.append((position, item))
        if len(selected) >= limit:
            return [item for _, item in selected]

    # A shelf deep in one franchise can cap away nearly everything, and a
    # slightly repetitive row beats an empty one.
    for entry in overflow:
        if len(selected) >= limit:
            break
        selected.append(entry)

    selected.sort(key=lambda entry: entry[0])
    return [item for _, item in selected]
