"""Declarative registry of the multi-value ROM filters.

Every entry here is one filter the gallery, the ROM list endpoint and smart
collections all share. Keeping the name, the column it matches on and the way
it matches in one place means the query builder, the join it needs and the
request schema are all derived from the same row instead of being restated.

The columns are the `roms_facets` mirror rather than `roms` or the
`roms_metadata` view over it. Both of those carry the raw provider-metadata
blobs inline, so matching against them reads the whole wide table; the mirror
holds the same values in a few MB. See `RomFacets`.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import QueryableAttribute

from logger.logger import log
from models.rom import RomFacets


class FilterKind(StrEnum):
    """How a filter's selected values are matched against its column."""

    # Column holds a JSON array; a rom matches when the arrays intersect.
    JSON_ARRAY = "json_array"
    # Column holds one scalar; a rom matches when it is among the values.
    SCALAR_IN = "scalar_in"
    # Values name metadata providers, each matched against its own id column,
    # so the spec carries no single column of its own.
    PROVIDER_IDS = "provider_ids"


@dataclass(frozen=True)
class RomFilterSpec:
    name: str
    kind: FilterKind
    column: QueryableAttribute | None = None


# Order is the order the filters narrow the query, so the generated WHERE
# clause keeps the shape it had before this was a registry. Every filter reads
# `roms_facets`, so applying any of them costs the query one join.
ROM_FILTER_SPECS: tuple[RomFilterSpec, ...] = (
    RomFilterSpec("genres", FilterKind.JSON_ARRAY, RomFacets.genres),
    RomFilterSpec("franchises", FilterKind.JSON_ARRAY, RomFacets.franchises),
    RomFilterSpec("collections", FilterKind.JSON_ARRAY, RomFacets.collections),
    RomFilterSpec("companies", FilterKind.JSON_ARRAY, RomFacets.companies),
    RomFilterSpec("publishers", FilterKind.JSON_ARRAY, RomFacets.publishers),
    RomFilterSpec("developers", FilterKind.JSON_ARRAY, RomFacets.developers),
    RomFilterSpec("age_ratings", FilterKind.JSON_ARRAY, RomFacets.age_ratings),
    RomFilterSpec("regions", FilterKind.JSON_ARRAY, RomFacets.regions),
    RomFilterSpec("languages", FilterKind.JSON_ARRAY, RomFacets.languages),
    RomFilterSpec("player_counts", FilterKind.SCALAR_IN, RomFacets.player_count),
    RomFilterSpec("metadata_providers", FilterKind.PROVIDER_IDS),
    RomFilterSpec("tags", FilterKind.JSON_ARRAY, RomFacets.tags),
)

# `statuses` is absent above on purpose: it matches against RomUser, is applied
# after the grouping window rather than with the rest, and carries the default
# "hide hidden roms" behaviour, so `filter_roms` owns it directly. It is still
# one of the filters a client selects values for.


# Filters whose criteria were stored as a single value before they accepted
# several, under a `selected_*` key.
_LEGACY_CRITERIA_KEYS: dict[str, str] = {
    "genres": "selected_genre",
    "franchises": "selected_franchise",
    "collections": "selected_collection",
    "companies": "selected_company",
    "age_ratings": "selected_age_rating",
    "regions": "selected_region",
    "languages": "selected_language",
    "tags": "selected_tag",
    "statuses": "selected_status",
}

# Every field holding a list of selected values, so the stored-criteria path
# can coerce a bare scalar into the list the field expects.
_LIST_FIELDS: tuple[str, ...] = (*(spec.name for spec in ROM_FILTER_SPECS), "statuses")

# The fields that pick a slice of the library rather than narrowing within one.
_SCOPE_FIELDS: tuple[str, ...] = (
    "search_term",
    "platform_ids",
    "collection_id",
    "virtual_collection_id",
    "smart_collection_id",
)

# Grouping changes how rows collapse, not which rows match, and a logic
# operator only matters when its own filter is set.
_UNFILTERED_FIELDS: frozenset[str] = frozenset(
    {"group_by_meta_id", *(f"{name}_logic" for name in _LIST_FIELDS)}
)


class RomFilterParams(BaseModel):
    """The filter vocabulary a client can send, shared by every surface.

    Used directly as the query-parameter model of the ROM list endpoint, and
    rebuilt from a smart collection's stored criteria, so both narrow the
    library through one set of names rather than two that can drift.
    """

    search_term: Annotated[
        str | None,
        Field(description="Search term to filter roms."),
    ] = None
    platform_ids: Annotated[
        list[int] | None,
        Field(
            description="Platform internal ids. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    collection_id: Annotated[
        int | None,
        Field(description="Collection internal id.", ge=1),
    ] = None
    virtual_collection_id: Annotated[
        str | None,
        Field(description="Virtual collection internal id."),
    ] = None
    smart_collection_id: Annotated[
        int | None,
        Field(description="Smart collection internal id.", ge=1),
    ] = None
    matched: Annotated[
        bool | None,
        Field(description="Whether the rom matched at least one metadata source."),
    ] = None
    favorite: Annotated[
        bool | None,
        Field(description="Whether the rom is marked as favorite."),
    ] = None
    duplicate: Annotated[
        bool | None,
        Field(description="Whether the rom is marked as duplicate."),
    ] = None
    last_played: Annotated[
        bool | None,
        Field(
            description="Whether the rom has a last played value for the current user."
        ),
    ] = None
    playable: Annotated[
        bool | None,
        Field(description="Whether the rom is playable from the browser."),
    ] = None
    missing: Annotated[
        bool | None,
        Field(description="Whether the rom is missing from the filesystem."),
    ] = None
    physical: Annotated[
        bool | None,
        Field(description="Whether the rom is a physical copy with no file."),
    ] = None
    has_ra: Annotated[
        bool | None,
        Field(description="Whether the rom has RetroAchievements data."),
    ] = None
    has_saves: Annotated[
        bool | None,
        Field(description="Whether the rom has saves for the current user."),
    ] = None
    has_states: Annotated[
        bool | None,
        Field(description="Whether the rom has save states for the current user."),
    ] = None
    verified: Annotated[
        bool | None,
        Field(description="Whether the rom is verified by Hasheous."),
    ] = None
    has_soundtrack: Annotated[
        bool | None,
        Field(description="Whether the rom has any soundtrack files."),
    ] = None
    group_by_meta_id: Annotated[
        bool,
        Field(
            description="Whether to group roms by metadata ID (IGDB / Moby / ScreenScraper / RetroAchievements / LaunchBox)."
        ),
    ] = False
    genres: Annotated[
        list[str] | None,
        Field(
            description="Associated genre. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    franchises: Annotated[
        list[str] | None,
        Field(
            description="Associated franchise. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    collections: Annotated[
        list[str] | None,
        Field(
            description="Associated collection. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    companies: Annotated[
        list[str] | None,
        Field(
            description="Associated company. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    publishers: Annotated[
        list[str] | None,
        Field(
            description="Associated publisher. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    developers: Annotated[
        list[str] | None,
        Field(
            description="Associated developer. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    age_ratings: Annotated[
        list[str] | None,
        Field(
            description="Associated age rating. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    statuses: Annotated[
        list[str] | None,
        Field(
            description="Game status, set by the current user. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    regions: Annotated[
        list[str] | None,
        Field(
            description="Associated region tag. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    languages: Annotated[
        list[str] | None,
        Field(
            description="Associated language tag. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    player_counts: Annotated[
        list[str] | None,
        Field(
            description="Associated player count. Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    metadata_providers: Annotated[
        list[str] | None,
        Field(
            description="Matched metadata provider (igdb, moby, ss, ra, launchbox, hasheous, flashpoint, hltb, demozoo, pouet, csdb, steam, gamelist, libretro). Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    tags: Annotated[
        list[str] | None,
        Field(
            description="Associated custom tag (parsed from the filename, e.g. Proto, Beta, Demo). Multiple values are allowed by repeating the parameter, and results that match any of the values will be returned."
        ),
    ] = None
    genres_logic: Annotated[
        str,
        Field(
            description="Logic operator for genres filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    franchises_logic: Annotated[
        str,
        Field(
            description="Logic operator for franchises filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    collections_logic: Annotated[
        str,
        Field(
            description="Logic operator for collections filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    companies_logic: Annotated[
        str,
        Field(
            description="Logic operator for companies filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    publishers_logic: Annotated[
        str,
        Field(
            description="Logic operator for publishers filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    developers_logic: Annotated[
        str,
        Field(
            description="Logic operator for developers filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    age_ratings_logic: Annotated[
        str,
        Field(
            description="Logic operator for age ratings filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    statuses_logic: Annotated[
        str,
        Field(
            description="Logic operator for statuses filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    regions_logic: Annotated[
        str,
        Field(
            description="Logic operator for regions filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    languages_logic: Annotated[
        str,
        Field(
            description="Logic operator for languages filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    player_counts_logic: Annotated[
        str,
        Field(
            description="Logic operator for player counts filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    metadata_providers_logic: Annotated[
        str,
        Field(
            description="Logic operator for metadata providers filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    tags_logic: Annotated[
        str,
        Field(
            description="Logic operator for tags filter: 'any' (OR), 'all' (AND) or 'none' (NOT)."
        ),
    ] = "any"
    hltb_main_story_min: Annotated[
        int | None,
        Field(
            description="Minimum HowLongToBeat main story time, in seconds. Roms without a HowLongToBeat time are excluded.",
            ge=0,
        ),
    ] = None
    hltb_main_story_max: Annotated[
        int | None,
        Field(
            description="Maximum HowLongToBeat main story time, in seconds. Roms without a HowLongToBeat time are excluded.",
            ge=0,
        ),
    ] = None

    @classmethod
    def from_stored_criteria(cls, criteria: Mapping[str, Any]) -> "RomFilterParams":
        """Build from a smart collection's stored `filter_criteria`.

        `smart_collection_id` is dropped: the create dialog records the route it
        was opened from, so a smart collection built while viewing another one
        carries that id, and following it would nest (and could cycle).
        """
        values: dict[str, Any] = dict(criteria)
        values.pop("smart_collection_id", None)

        for field, legacy_key in _LEGACY_CRITERIA_KEYS.items():
            values[field] = values.get(field) or values.get(legacy_key)

        for field in _LIST_FIELDS:
            value = values.get(field)
            values[field] = [value] if isinstance(value, str) else (value or None)

        if values.get("platform_ids") is None and (
            platform_id := values.get("platform_id")
        ):
            values["platform_ids"] = [platform_id]

        return cls._validate_tolerantly(values)

    @classmethod
    def _validate_tolerantly(cls, values: dict[str, Any]) -> "RomFilterParams":
        """Validate, dropping the entries that fail rather than raising.

        `filter_criteria` is stored as free-form JSON, so a row can hold a value
        no field accepts: an out-of-range bound, a null where the model wants a
        string, a shape an older client wrote. Every caller reads these rows in
        a loop over all smart collections, so raising on one would stop the rest
        from refreshing at all. A filter that cannot be honoured is dropped,
        which is what the criteria reader did before it validated anything.
        """
        while True:
            try:
                return cls.model_validate(values)
            except ValidationError as error:
                dropped = {
                    str(err["loc"][0])
                    for err in error.errors()
                    if err["loc"] and str(err["loc"][0]) in values
                }
                if not dropped:
                    log.warning("Discarding unusable smart collection criteria")
                    return cls()
                for field in dropped:
                    del values[field]

    def selected(self, name: str) -> tuple[Sequence[str] | None, str]:
        """The values chosen for a multi-value filter, with its logic operator."""
        return getattr(self, name), getattr(self, f"{name}_logic")

    def has_scope(self) -> bool:
        """Whether anything picks a slice of the library smaller than all of it."""
        return any(getattr(self, field) for field in _SCOPE_FIELDS)

    def has_filters(self) -> bool:
        """Whether anything narrows the results within that slice.

        Read off the model's own fields rather than a hand-kept list, so a
        filter added later counts here without anyone remembering to. Callers
        gate a shared cache on this, so a filter missing from it would serve one
        user's narrowed library to everyone.
        """
        return any(
            (value := getattr(self, field)) is not None and value != []
            for field in type(self).model_fields
            if field not in _SCOPE_FIELDS and field not in _UNFILTERED_FIELDS
        )

    def scope_only(self) -> "RomFilterParams":
        """Just the fields that choose which slice of the library is in view.

        The filter dropdowns list the values still reachable within that slice,
        so they are computed with the applied filters dropped.
        """
        return RomFilterParams(
            **{field: getattr(self, field) for field in _SCOPE_FIELDS}
        )
