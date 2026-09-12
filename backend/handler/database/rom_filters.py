"""Declarative registry of the multi-value ROM filters.

Every entry here is one filter the gallery, the ROM list endpoint and smart
collections all share. Keeping the name, the column it matches on and the way
it matches in one place means the query builder, the join it needs and the
request schema are all derived from the same row instead of being restated.
"""

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.orm import QueryableAttribute

from models.rom import Rom, RomMetadata


class FilterKind(StrEnum):
    """How a filter's selected values are matched against its column."""

    # Column holds a JSON array; a rom matches when the arrays intersect.
    JSON_ARRAY = "json_array"
    # Column holds one scalar; a rom matches when it is among the values.
    SCALAR_IN = "scalar_in"
    # Values name metadata providers, matched against their id columns on Rom.
    PROVIDER_IDS = "provider_ids"


@dataclass(frozen=True)
class RomFilterSpec:
    name: str
    kind: FilterKind
    column: QueryableAttribute | None = None

    @property
    def needs_metadata_join(self) -> bool:
        """Whether matching reads `RomMetadata`, which the query has to join."""
        return self.column is not None and self.column.class_ is RomMetadata


# Order is the order the filters narrow the query, so the generated WHERE
# clause keeps the shape it had before this was a registry.
ROM_FILTER_SPECS: tuple[RomFilterSpec, ...] = (
    RomFilterSpec("genres", FilterKind.JSON_ARRAY, RomMetadata.genres),
    RomFilterSpec("franchises", FilterKind.JSON_ARRAY, RomMetadata.franchises),
    RomFilterSpec("collections", FilterKind.JSON_ARRAY, RomMetadata.collections),
    RomFilterSpec("companies", FilterKind.JSON_ARRAY, RomMetadata.companies),
    RomFilterSpec("publishers", FilterKind.JSON_ARRAY, RomMetadata.publishers),
    RomFilterSpec("developers", FilterKind.JSON_ARRAY, RomMetadata.developers),
    RomFilterSpec("age_ratings", FilterKind.JSON_ARRAY, RomMetadata.age_ratings),
    RomFilterSpec("regions", FilterKind.JSON_ARRAY, Rom.regions),
    RomFilterSpec("languages", FilterKind.JSON_ARRAY, Rom.languages),
    RomFilterSpec("player_counts", FilterKind.SCALAR_IN, RomMetadata.player_count),
    RomFilterSpec("metadata_providers", FilterKind.PROVIDER_IDS),
    RomFilterSpec("tags", FilterKind.JSON_ARRAY, Rom.tags),
)

# `statuses` is missing on purpose: it matches against RomUser, is applied
# after the grouping window rather than with the rest, and carries the default
# "hide hidden roms" behaviour. `filter_roms` owns it directly.
ROM_FILTER_NAMES: frozenset[str] = frozenset(spec.name for spec in ROM_FILTER_SPECS)
