"""The read path behind both recommendation surfaces.

"Similar games" and the personalised feed differ only in where their ranking
comes from; everything after that (rank deep, hydrate, drop what the viewer
cannot see, cap by series, truncate) is shared.
"""

from __future__ import annotations

from collections.abc import Sequence

from handler.auth.permissions import ResolvedPermissions
from handler.database import db_recommendation_handler
from handler.recommendation.diversity import OVERFETCH_FACTOR, cap_by_series
from handler.recommendation.feed import (
    FeedBuilder,
    RecommendedRom,
    get_cached_feed,
    hydrate_roms,
    set_cached_feed,
)
from models.rom import Rom

# Extra depth for a viewer whose visibility rules hide ROMs: ranking exactly
# `limit` and filtering afterwards hands them a short row, or an empty one.
VISIBILITY_OVERFETCH = 3


def similar_roms(
    rom_id: int, *, limit: int, permissions: ResolvedPermissions
) -> list[RecommendedRom]:
    """The library's closest games to one ROM, best first."""
    edges = db_recommendation_handler.get_similar_rom_edges(
        rom_id, limit=_ranked_depth(limit, permissions)
    )
    roms = _visible_roms([edge.rom_id for edge in edges], permissions)

    # Without the cap this section is just the franchise the user is already
    # looking at: five Metroid games for Super Metroid.
    selected = cap_by_series(edges, lambda edge: roms.get(edge.rom_id), limit=limit)

    return [
        RecommendedRom(rom=roms[edge.rom_id], score=edge.score, reasons=edge.reasons)
        for edge in selected
    ]


def recommended_roms(
    user_id: int,
    *,
    limit: int,
    permissions: ResolvedPermissions,
    refresh: bool = False,
) -> list[RecommendedRom]:
    """The personalised feed, ranked on demand and cached per user.

    The cache lives here rather than in the endpoint so no caller can rank a
    feed without populating it, or read a stale one after an exclusion changes.
    """
    ranked_limit = (
        limit * VISIBILITY_OVERFETCH if _hides_anything(permissions) else limit
    )

    feed = None if refresh else get_cached_feed(user_id, ranked_limit)
    if feed is None:
        feed = FeedBuilder(user_id).build(limit=ranked_limit)
        set_cached_feed(user_id, ranked_limit, feed)

    # Visibility is applied after the cache so a permission change takes effect
    # without waiting for the entry to expire.
    visible = [
        item
        for item in feed
        if permissions.can_see_rom(item.rom.id, item.rom.platform_id)
    ]
    return visible[:limit]


def _hides_anything(permissions: ResolvedPermissions) -> bool:
    return not permissions.is_admin and bool(
        permissions.hidden_rom_ids or permissions.hidden_platform_ids
    )


def _ranked_depth(limit: int, permissions: ResolvedPermissions) -> int:
    """How deep to rank so `limit` entries survive the cuts below."""
    depth = limit * OVERFETCH_FACTOR
    return depth * VISIBILITY_OVERFETCH if _hides_anything(permissions) else depth


def _visible_roms(
    rom_ids: Sequence[int], permissions: ResolvedPermissions
) -> dict[int, Rom]:
    """Hydrate through the shared load path, keeping what the viewer can see."""
    return {
        rom_id: rom
        for rom_id, rom in hydrate_roms(rom_ids).items()
        if permissions.can_see_rom(rom.id, rom.platform_id)
    }
