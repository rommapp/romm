"""Release types: what kind of release a ROM is, beyond a standard retail game."""

from __future__ import annotations

import enum
import re
from collections.abc import Iterable, Mapping
from typing import Any, Final


class ReleaseType(enum.StrEnum):
    HOMEBREW = "homebrew"
    HACK = "hack"
    COLOR_PATCH = "color_patch"
    TRANSLATION = "translation"
    FAN_GAME = "fan_game"
    TOTAL_CONVERSION = "total_conversion"
    RANDOMIZER = "randomizer"
    DEMAKE = "demake"
    PORT = "port"
    PROTOTYPE = "prototype"
    UTILITY = "utility"
    TECH_DEMO = "tech_demo"
    UNLICENSED = "unlicensed"


# The ROM columns `compute_release_types` reads, so writers know when to recompute it.
RELEASE_TYPE_SOURCE_COLUMNS: Final = ("manual_metadata", "tags", "regions")

# Filename and dump-flag tags that name a release type, as the dump sets spell
# them: "(Hack)", GoodTools "[h1]", "(Beta 2)", No-Intro "(Proto)".
_TAG_PATTERNS: Final = (
    (re.compile(r"hack(ed)?|h\d*", re.I), ReleaseType.HACK),
    (re.compile(r"translation", re.I), ReleaseType.TRANSLATION),
    (re.compile(r"(alpha|beta|proto(type)?)( \d+)?", re.I), ReleaseType.PROTOTYPE),
    (re.compile(r"homebrew", re.I), ReleaseType.HOMEBREW),
)

# The filename parser files GoodTools' "(Unl)" under the regions it lists.
_REGION_RELEASE_TYPES: Final = {"Unlicensed": ReleaseType.UNLICENSED}

_ORDER: Final = {release_type: i for i, release_type in enumerate(ReleaseType)}


def release_types_from_tags(
    tags: Iterable[str], regions: Iterable[str] = ()
) -> list[ReleaseType]:
    """The release types a ROM's filename and dump tags, and its regions, name."""
    from_tags = (
        release_type
        for tag in tags
        if isinstance(tag, str)
        for pattern, release_type in _TAG_PATTERNS
        if pattern.fullmatch(tag.strip())
    )
    from_regions = (
        _REGION_RELEASE_TYPES[region]
        for region in regions
        if region in _REGION_RELEASE_TYPES
    )
    return _ordered([*from_tags, *from_regions])


def compute_release_types(metadata: Mapping[str, Any]) -> list[str]:
    """Precompute `Rom.release_types`, where a non-empty manual list replaces
    the types the tags imply, as the other manual metadata lists do.

    Args:
        metadata: Each `RELEASE_TYPE_SOURCE_COLUMNS` column's value, by column name.
    """
    manual = metadata.get("manual_metadata")
    manual_types = manual.get("release_types") if isinstance(manual, Mapping) else None
    if isinstance(manual_types, list) and manual_types:
        return [str(t) for t in _ordered(_known(manual_types))]
    derived = release_types_from_tags(
        metadata.get("tags") or [], metadata.get("regions") or []
    )
    return [str(t) for t in derived]


def _known(values: Iterable[Any]) -> Iterable[ReleaseType]:
    for value in values:
        try:
            yield ReleaseType(value)
        except ValueError:
            continue


def _ordered(release_types: Iterable[ReleaseType]) -> list[ReleaseType]:
    return sorted(set(release_types), key=_ORDER.__getitem__)
