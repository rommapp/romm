"""Unit tests for the diversity caps applied when serving recommendations.

`cap_by_series` only reads `rom.metadatum` and `rom.platform_id`, so these use
lightweight stand-ins rather than database rows.
"""

from dataclasses import dataclass, field
from typing import cast

from handler.recommendation.diversity import (
    cap_by_series,
    series_keys,
)
from models.rom import Rom


@dataclass
class FakeMetadata:
    franchises: list[str] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)


@dataclass
class FakeRom:
    id: int
    metadatum: FakeMetadata | None = None
    platform_id: int = 1


def rom(
    rom_id: int,
    franchise: str = "",
    collection: str = "",
    franchises: list[str] | None = None,
    platform_id: int = 1,
) -> FakeRom:
    return FakeRom(
        id=rom_id,
        platform_id=platform_id,
        metadatum=FakeMetadata(
            franchises=(
                franchises
                if franchises is not None
                else ([franchise] if franchise else [])
            ),
            collections=[collection] if collection else [],
        ),
    )


def resolve(roms: dict[int, FakeRom]):
    return lambda rom_id: roms.get(rom_id)


def test_caps_each_series_at_the_limit():
    """Two per series, with enough other candidates to fill the list.

    `limit` is set to exactly what the cap yields; asking for more would pull
    the capped-out entries back in via the backfill below.
    """
    roms = {i: rom(i, franchise="Metroid") for i in range(1, 4)}
    roms.update({i: rom(i, franchise="Castlevania") for i in range(4, 7)})

    selected = cap_by_series(list(roms), resolve(roms), limit=4, max_per_series=2)

    assert selected == [1, 2, 4, 5]


def test_games_without_a_series_are_never_capped():
    """Otherwise an unmatched shelf collapses to two results."""
    roms = {i: rom(i) for i in range(1, 6)}

    selected = cap_by_series(list(roms), resolve(roms), limit=5, max_per_series=2)

    assert len(selected) == 5


def test_capped_out_entries_backfill_a_short_list():
    """A shelf deep in one franchise must not return a near-empty section."""
    roms = {i: rom(i, franchise="Sonic") for i in range(1, 7)}

    selected = cap_by_series(list(roms), resolve(roms), limit=4, max_per_series=2)

    assert len(selected) == 4


def test_backfilled_entries_keep_their_original_order():
    """Backfill appends by rank, so the list must not end up out of order."""
    roms = {1: rom(1, franchise="Sonic"), 2: rom(2, franchise="Sonic")}
    roms[3] = rom(3, franchise="Sonic")
    roms[4] = rom(4, franchise="Mario")

    selected = cap_by_series([1, 2, 3, 4], resolve(roms), limit=4, max_per_series=2)

    # 3 is capped out then backfilled; it must land before 4, not after.
    assert selected == [1, 2, 3, 4]


def test_stops_at_the_limit():
    roms = {i: rom(i, franchise=f"F{i}") for i in range(1, 10)}

    assert len(cap_by_series(list(roms), resolve(roms), limit=3)) == 3


def test_unresolvable_items_are_dropped():
    """Permission filtering removes ROMs, leaving edges that resolve to nothing."""
    roms = {1: rom(1, franchise="Metroid")}

    assert cap_by_series([1, 2, 3], resolve(roms), limit=5) == [1]


def test_series_keys_returns_every_franchise_and_collection():
    entry = rom(1, collection="Madden NFL", franchises=["Madden", "NFL"])

    assert series_keys(cast("Rom", entry)) == {"Madden", "NFL", "Madden NFL"}


def test_a_series_listed_under_several_names_shares_one_allowance():
    """Regression: four Madden games cleared a cap of two.

    IGDB lists franchises in no stable order, so some Madden titles resolved
    to "Madden" and others to "NFL". Keying on one entry gave each spelling
    its own allowance, and the section filled with a single series.
    """
    roms = {
        1: rom(1, franchises=["Madden", "NFL"]),
        2: rom(2, franchises=["Madden", "NFL"]),
        3: rom(3, franchises=["NFL", "Madden"]),
        4: rom(4, franchises=["NFL"]),
        5: rom(5, franchise="Tecmo Bowl"),
    }

    selected = cap_by_series([1, 2, 3, 4, 5], resolve(roms), limit=3, max_per_series=2)

    # Two from the shared series, then the unrelated game -- not a third Madden.
    assert selected == [1, 2, 5]


def test_overlapping_series_still_backfills_when_nothing_else_exists():
    roms = {i: rom(i, franchises=["Madden", "NFL"]) for i in range(1, 5)}

    assert len(cap_by_series(list(roms), resolve(roms), limit=4, max_per_series=2)) == 4


def test_a_platform_can_be_capped_too():
    """The feed shares this path and does not want one console owning the row."""
    roms = {i: rom(i, platform_id=1) for i in range(1, 4)}
    roms.update({i: rom(i, platform_id=2) for i in range(4, 7)})

    selected = cap_by_series(list(roms), resolve(roms), limit=4, max_per_platform=2)

    assert selected == [1, 2, 4, 5]


def test_the_platform_cap_is_off_unless_asked_for():
    """A single game's "Similar games" is happy to be all one platform."""
    roms = {i: rom(i, platform_id=1) for i in range(1, 5)}

    assert len(cap_by_series(list(roms), resolve(roms), limit=4)) == 4


def test_a_platform_capped_entry_backfills_a_short_list():
    roms = {i: rom(i, platform_id=1) for i in range(1, 6)}

    selected = cap_by_series(list(roms), resolve(roms), limit=4, max_per_platform=2)

    assert len(selected) == 4
