"""Unit tests for the per-series cap applied when serving recommendations.

`primary_series` only reads `rom.metadatum`, so these use lightweight stand-ins
rather than database rows.
"""

from dataclasses import dataclass, field

from handler.recommendation.diversity import cap_by_series, primary_series


@dataclass
class FakeMetadata:
    franchises: list[str] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)


@dataclass
class FakeRom:
    id: int
    metadatum: FakeMetadata | None = None


def rom(rom_id: int, franchise: str = "", collection: str = "") -> FakeRom:
    return FakeRom(
        id=rom_id,
        metadatum=FakeMetadata(
            franchises=[franchise] if franchise else [],
            collections=[collection] if collection else [],
        ),
    )


def resolve(roms: dict[int, FakeRom]):
    return lambda rom_id: roms.get(rom_id)


def test_primary_series_prefers_the_broader_franchise():
    """Keying on the narrower collection let four Metroids through as two pairs."""
    entry = rom(1, franchise="Metroid", collection="Metroid Prime")

    assert primary_series(entry) == "Metroid"


def test_primary_series_falls_back_to_collection():
    assert primary_series(rom(1, collection="Sonic the Hedgehog")) == (
        "Sonic the Hedgehog"
    )


def test_primary_series_is_none_without_metadata():
    assert primary_series(FakeRom(id=1, metadatum=None)) is None
    assert primary_series(rom(1)) is None


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
