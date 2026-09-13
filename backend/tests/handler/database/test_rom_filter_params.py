"""The filter vocabulary, and the predicate that decides what may be cached.

The gallery's sidecar caches are keyed on user/order/grouping but not on the
filters, so `/api/roms` only reads and writes them for an unnarrowed library.
`has_filters` is what draws that line: a filter it fails to count would let one
user's narrowed gallery be served to everyone under the shared key.
"""

from typing import Any

import pytest
from handler.database.rom_filters import (
    _SCOPE_FIELDS,
    _UNFILTERED_FIELDS,
    ROM_FILTER_SPECS,
    RomFilterParams,
)
from models.rom import RomFacets

# A value that counts as "selected", per field type.
SAMPLE_VALUES: dict[str, Any] = {
    "list[str] | None": ["any-value"],
    "list[int] | None": [1],
    "bool | None": True,
    "bool": True,
    "int | None": 1,
    "str | None": "any-value",
    "str": "all",
}


def _sample_for(annotation: Any) -> Any:
    key = str(annotation).replace("typing.", "").replace("Optional", "")
    for name, value in SAMPLE_VALUES.items():
        if key == name:
            return value
    raise AssertionError(f"no sample value for annotation {annotation!r}")


NARROWING_FIELDS = [
    name
    for name in RomFilterParams.model_fields
    if name not in _SCOPE_FIELDS and name not in _UNFILTERED_FIELDS
]


class TestHasFilters:
    def test_nothing_selected_is_not_filtered(self):
        assert RomFilterParams().has_filters() is False

    @pytest.mark.parametrize("field", NARROWING_FIELDS)
    def test_every_narrowing_field_is_counted(self, field: str):
        params = RomFilterParams(
            **{field: _sample_for(RomFilterParams.model_fields[field].annotation)}
        )

        assert params.has_filters() is True

    def test_a_false_flag_is_still_a_filter(self):
        # `matched=False` selects the unmatched roms; it is not "unset".
        assert RomFilterParams(matched=False).has_filters() is True

    def test_an_empty_list_is_not_a_filter(self):
        assert RomFilterParams(genres=[]).has_filters() is False

    def test_a_logic_operator_alone_is_not_a_filter(self):
        assert RomFilterParams(genres_logic="all").has_filters() is False

    def test_grouping_is_not_a_filter(self):
        # Grouping collapses matching rows; it does not change which ones match.
        assert RomFilterParams(group_by_meta_id=True).has_filters() is False

    def test_scope_does_not_count_as_a_filter(self):
        params = RomFilterParams(platform_ids=[1])

        assert params.has_scope() is True
        assert params.has_filters() is False


class TestScopeOnly:
    def test_it_keeps_the_scope_and_drops_the_filters(self):
        params = RomFilterParams(
            platform_ids=[1],
            search_term="mario",
            genres=["Shooter"],
            matched=True,
        )

        scoped = params.scope_only()

        assert scoped.platform_ids == [1]
        assert scoped.search_term == "mario"
        assert scoped.genres is None
        assert scoped.matched is None


class TestFromStoredCriteria:
    def test_it_reads_the_legacy_single_value_keys(self):
        criteria = RomFilterParams.from_stored_criteria(
            {"selected_genre": "Shooter", "platform_id": 7}
        )

        assert criteria.genres == ["Shooter"]
        assert criteria.platform_ids == [7]

    def test_current_keys_win_over_the_legacy_ones(self):
        criteria = RomFilterParams.from_stored_criteria(
            {"genres": ["RPG"], "selected_genre": "Shooter"}
        )

        assert criteria.genres == ["RPG"]

    def test_it_ignores_keys_that_are_not_filters(self):
        criteria = RomFilterParams.from_stored_criteria(
            {"order_by": "name", "matched": True}
        )

        assert criteria.matched is True

    def test_it_drops_a_nested_smart_collection(self):
        criteria = RomFilterParams.from_stored_criteria(
            {"smart_collection_id": 42, "matched": True}
        )

        assert criteria.smart_collection_id is None
        assert criteria.matched is True

    # `filter_criteria` is stored as free-form JSON, so any of these can sit in
    # a real row. Every caller reads them in a loop over all smart collections,
    # so one raising would stop every later collection from refreshing.
    @pytest.mark.parametrize(
        "unusable",
        [
            {"collection_id": 0},
            {"hltb_main_story_min": -1},
            {"group_by_meta_id": None},
            {"platform_ids": ["not-an-id"]},
            {"genres_logic": None},
            {"statuses": {"not": "a list"}},
        ],
    )
    def test_an_unusable_value_is_dropped_rather_than_raised(self, unusable: dict):
        criteria = RomFilterParams.from_stored_criteria({"genres": ["RPG"], **unusable})

        assert criteria.genres == ["RPG"]
        for field in unusable:
            assert (
                getattr(criteria, field)
                == RomFilterParams.model_fields[field].get_default()
            )

    def test_a_wholly_unusable_row_yields_an_empty_filter(self):
        criteria = RomFilterParams.from_stored_criteria({"matched": "maybe"})

        assert criteria == RomFilterParams()
        assert criteria.has_filters() is False


class TestRegistryColumns:
    def test_every_filter_matches_against_the_facets_mirror(self):
        """Filters must not read `roms` or the `roms_metadata` view over it.

        Both carry the raw provider-metadata blobs inline, so matching against
        them reads the whole wide table: on a 40k-game library that made the
        gallery's count and id-index queries 5-8x slower than the same
        predicates against the narrow mirror.
        """
        for spec in ROM_FILTER_SPECS:
            if spec.column is None:  # metadata_providers, matched on id columns
                continue

            assert (
                spec.column.class_ is RomFacets
            ), f"{spec.name} reads {spec.column.class_.__name__}"
