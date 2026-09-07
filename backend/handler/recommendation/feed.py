"""Builds a user's personalised recommendation feed.

Computed on demand from the precomputed similarity edges plus live activity,
rather than precomputed per user: a feed built nightly would ignore the game
someone played an hour ago, which is exactly the signal that matters most.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Final

from handler.database import db_recommendation_handler, db_rom_handler
from handler.database.recommendations_handler import UserAffinityRow
from handler.recommendation.diversity import OVERFETCH_FACTOR, cap_by_series
from handler.recommendation.scoring import Facet
from handler.redis_handler import sync_cache
from logger.logger import log
from models.rom import Rom, RomUserStatus
from utils.datetime import to_utc

# The user rating scale is 1-10; 5.5 is the indifference point, so anything
# below it pushes similar games *away* rather than merely not pulling them in.
NEUTRAL_RATING: Final = 5.5
MAX_RATING: Final = 10.0

# Playtime saturates: the difference between 1h and 10h says a lot, the
# difference between 100h and 200h says almost nothing.
PLAYTIME_SATURATION_HOURS: Final = 20.0

# Taste drifts. A game played last week should steer the feed more than one
# finished two years ago, without the old one falling off entirely.
RECENCY_HALFLIFE_DAYS: Final = 60.0
MIN_RECENCY_FACTOR: Final = 0.15

STATUS_AFFINITY: Final[dict[str, float]] = {
    RomUserStatus.COMPLETED_100.value: 1.0,
    RomUserStatus.FINISHED.value: 0.8,
    RomUserStatus.RETIRED.value: 0.4,
    RomUserStatus.INCOMPLETE.value: 0.3,
}

# Games the user has already played still belong in the feed (a sequel to
# something you finished is a fine suggestion), but an unplayed game you own
# is the outcome this feature exists to produce.
PLAYED_NOVELTY_FACTOR: Final = 0.3

# Disliked games steer, but less forcefully than loved ones.
NEGATIVE_SEED_DAMPING: Final = 0.5

# Ceiling applied during diversification, so one platform cannot own the row.
# The per-series ceiling is shared with the similar-games surface.
MAX_PER_PLATFORM: Final = 4

# Seeds are read in descending affinity; beyond this the contribution is noise.
MAX_SEEDS: Final = 60

FEED_CACHE_TTL_SECONDS: Final = 900
FEED_CACHE_PREFIX: Final = "recommendations:feed"
# Bumped when the similarity graph is rebuilt, which invalidates every user.
_GRAPH_VERSION_KEY: Final = f"{FEED_CACHE_PREFIX}:version"


@dataclass
class RecommendedRom:
    rom: Rom
    score: float
    reasons: list[dict[str, str]] = field(default_factory=list)
    seed_rom_id: int | None = None
    seed_rom_name: str | None = None


@dataclass
class _Candidate:
    rom_id: int
    score: float = 0.0
    best_seed_id: int | None = None
    best_seed_contribution: float = 0.0
    reasons: list[dict[str, str]] = field(default_factory=list)


def seed_affinity(row: UserAffinityRow, *, now: datetime | None = None) -> float:
    """How strongly one played game should steer the feed, in roughly [-1, 1].

    Negative for games the user rated below the midpoint, which is what lets
    the feed learn "not this kind of thing".
    """
    signals: list[float] = []

    if row.playtime_ms > 0:
        hours = row.playtime_ms / 3_600_000
        signals.append(
            min(1.0, math.log1p(hours) / math.log1p(PLAYTIME_SATURATION_HOURS))
        )

    if row.rating:
        # Maps 10 -> +1.0 and 1 -> -1.0, crossing zero at the scale midpoint.
        signals.append(
            max(
                -1.0,
                min(1.0, (row.rating - NEUTRAL_RATING) / (MAX_RATING - NEUTRAL_RATING)),
            )
        )

    if row.status and row.status in STATUS_AFFINITY:
        signals.append(STATUS_AFFINITY[row.status])

    if row.now_playing:
        signals.append(1.0)

    if not signals:
        # Played at some point, but nothing else is known about it.
        return (
            0.2 * _recency_factor(row.last_played, now=now) if row.last_played else 0.0
        )

    affinity = sum(signals) / len(signals)
    if affinity < 0:
        affinity *= NEGATIVE_SEED_DAMPING

    return affinity * _recency_factor(row.last_played, now=now)


def _recency_factor(
    last_played: datetime | None, *, now: datetime | None = None
) -> float:
    """Exponential decay on time since last played, floored so old loves persist."""
    if last_played is None:
        return MIN_RECENCY_FACTOR

    reference = now or datetime.now(timezone.utc)
    days = max(0.0, (reference - to_utc(last_played)).total_seconds() / 86_400)
    decayed = math.pow(0.5, days / RECENCY_HALFLIFE_DAYS)
    return max(MIN_RECENCY_FACTOR, decayed)


class FeedBuilder:
    """Ranks candidates for one user from the precomputed similarity graph."""

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    def build(self, limit: int = 20) -> list[RecommendedRom]:
        affinity_rows = db_recommendation_handler.get_user_affinity(self.user_id)

        seeds, excluded = self._partition(affinity_rows)
        if not seeds:
            return self._cold_start(limit, excluded)

        candidates = self._accumulate(seeds, excluded)
        if not candidates:
            return self._cold_start(limit, excluded)

        played_rom_ids = {
            row.rom_id for row in affinity_rows if row.last_played is not None
        }
        return self._rank(candidates, played_rom_ids, seeds, limit)

    # --- Stages ------------------------------------------------------------------

    def _partition(
        self, rows: Sequence[UserAffinityRow]
    ) -> tuple[dict[int, float], set[int]]:
        """Split the user's library interactions into seeds and hard exclusions."""
        seeds: dict[int, float] = {}
        excluded: set[int] = set()

        for row in rows:
            if row.hidden or row.status == RomUserStatus.NEVER_PLAYING.value:
                excluded.add(row.rom_id)
                # Never-played-on-purpose is a filtering decision, not a taste
                # signal, so it contributes nothing to the seed set.
                if row.status == RomUserStatus.NEVER_PLAYING.value:
                    continue

            affinity = seed_affinity(row)
            if abs(affinity) > 0.01:
                seeds[row.rom_id] = affinity

        # The seeds themselves are never their own recommendations.
        excluded.update(seeds)

        if len(seeds) > MAX_SEEDS:
            strongest = sorted(seeds.items(), key=lambda kv: -abs(kv[1]))[:MAX_SEEDS]
            seeds = dict(strongest)

        return seeds, excluded

    def _accumulate(
        self, seeds: dict[int, float], excluded: set[int]
    ) -> dict[int, _Candidate]:
        """Fan out from every seed, summing weighted edge scores per candidate."""
        edges = db_recommendation_handler.get_neighbours_for_roms(list(seeds))
        candidates: dict[int, _Candidate] = {}

        for seed_id, related_id, edge_score, reasons in edges:
            if related_id in excluded:
                continue

            contribution = edge_score * seeds[seed_id]
            candidate = candidates.get(related_id)
            if candidate is None:
                candidate = _Candidate(rom_id=related_id)
                candidates[related_id] = candidate

            candidate.score += contribution
            # Attribute the recommendation to whichever seed pulled hardest, so
            # "Because you played X" names the game that actually caused it.
            if contribution > candidate.best_seed_contribution:
                candidate.best_seed_contribution = contribution
                candidate.best_seed_id = seed_id
                candidate.reasons = list(reasons)

        return {
            rom_id: candidate
            for rom_id, candidate in candidates.items()
            if candidate.score > 0
        }

    def _rank(
        self,
        candidates: dict[int, _Candidate],
        played_rom_ids: set[int],
        seeds: dict[int, float],
        limit: int,
    ) -> list[RecommendedRom]:
        for candidate in candidates.values():
            if candidate.rom_id in played_rom_ids:
                candidate.score *= PLAYED_NOVELTY_FACTOR

        ordered = sorted(candidates.values(), key=lambda c: (-c.score, c.rom_id))[
            : limit * OVERFETCH_FACTOR
        ]

        roms = hydrate_roms([candidate.rom_id for candidate in ordered])
        seed_names = db_recommendation_handler.get_rom_names(
            [
                candidate.best_seed_id
                for candidate in ordered
                if candidate.best_seed_id is not None
            ]
        )

        chosen = cap_by_series(
            ordered,
            lambda candidate: roms.get(candidate.rom_id),
            limit=limit,
            max_per_platform=MAX_PER_PLATFORM,
        )

        return [
            RecommendedRom(
                rom=roms[candidate.rom_id],
                score=round(candidate.score, 6),
                reasons=candidate.reasons,
                seed_rom_id=candidate.best_seed_id,
                seed_rom_name=seed_names.get(candidate.best_seed_id or -1),
            )
            for candidate in chosen
        ]

    def _cold_start(self, limit: int, excluded: set[int]) -> list[RecommendedRom]:
        """No usable activity yet, so fall back to the library's best-reviewed."""
        log.debug(f"No recommendation seeds for user {self.user_id}, using fallback")

        rom_ids = db_recommendation_handler.get_fallback_rom_ids(
            limit, exclude_rom_ids=list(excluded)
        )
        roms = hydrate_roms(rom_ids)

        return [
            RecommendedRom(
                rom=roms[rom_id],
                score=0.0,
                reasons=[{"facet": Facet.TOP_RATED, "value": ""}],
            )
            for rom_id in rom_ids
            if rom_id in roms
        ]


def hydrate_roms(rom_ids: Sequence[int]) -> dict[int, Rom]:
    """Load ROMs through the shared `SimpleRomSchema` load path.

    Missing-from-disk ROMs are dropped here rather than in SQL, so the edge
    queries never have to join the wide `roms` table.
    """
    return {
        rom.id: rom
        for rom in db_rom_handler.get_roms_simple_by_ids(list(rom_ids))
        if not rom.missing_from_fs
    }


def get_cached_feed(user_id: int, limit: int) -> list[RecommendedRom] | None:
    """Read a cached feed, re-hydrating the ROMs so visibility stays live."""
    raw = sync_cache.get(_cache_key(user_id, limit))
    if not raw:
        return None

    try:
        entries: list[dict[str, Any]] = json.loads(raw)
    except (ValueError, TypeError):
        return None

    roms = hydrate_roms([entry["rom_id"] for entry in entries])

    return [
        RecommendedRom(
            rom=roms[entry["rom_id"]],
            score=entry["score"],
            reasons=entry.get("reasons") or [],
            seed_rom_id=entry.get("seed_rom_id"),
            seed_rom_name=entry.get("seed_rom_name"),
        )
        for entry in entries
        if entry["rom_id"] in roms
    ]


def set_cached_feed(user_id: int, limit: int, feed: Sequence[RecommendedRom]) -> None:
    """Cache only the ranking, never the ROM rows themselves."""
    payload = json.dumps(
        [
            {
                "rom_id": item.rom.id,
                "score": item.score,
                "reasons": item.reasons,
                "seed_rom_id": item.seed_rom_id,
                "seed_rom_name": item.seed_rom_name,
            }
            for item in feed
        ]
    )
    sync_cache.set(_cache_key(user_id, limit), payload, ex=FEED_CACHE_TTL_SECONDS)


def invalidate_cached_feed(user_id: int) -> None:
    sync_cache.incr(_user_version_key(user_id))


def invalidate_all_cached_feeds() -> None:
    """Drop every user's ranking, for when the graph underneath it changes."""
    sync_cache.incr(_GRAPH_VERSION_KEY)


def _version(key: str) -> str:
    raw = sync_cache.get(key)
    if isinstance(raw, bytes):
        return raw.decode()
    return str(raw) if raw is not None else "0"


def _user_version_key(user_id: int) -> str:
    return f"{FEED_CACHE_PREFIX}:version:{user_id}"


def _cache_key(user_id: int, limit: int) -> str:
    # Both versions ride in the key so invalidation is a single INCR rather
    # than a SCAN over a keyspace shared with the job queues and sessions.
    # Superseded entries are never read again and fall out on their own TTL.
    return (
        f"{FEED_CACHE_PREFIX}:g{_version(_GRAPH_VERSION_KEY)}"
        f":{user_id}:u{_version(_user_version_key(user_id))}:{limit}"
    )
