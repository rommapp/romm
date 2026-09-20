"""Builds the precomputed item-item similarity graph.

Run from the scheduled recommendations task, and incrementally after a scan.
A full build derives the whole graph from one consistent snapshot of the
library, because the IDF weighting that makes scores library-relative changes
as the shelf grows.
"""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any, Final

from handler.database import db_recommendation_handler
from handler.database.recommendations_handler import RomFeatureRow
from logger.logger import log

from .feed import invalidate_all_cached_feeds
from .scoring import (
    Facet,
    RomFeatures,
    blend,
    build_inverted_index,
    build_normalised_vectors,
    candidate_ids,
    compute_idf,
    content_similarity,
    extract_tokens,
    has_taste_signal,
    normalise_co_occurrence,
    shared_reasons,
    token_facet,
)

# Identity of a ROM no identity provider matched: nothing to collide on.
_NO_IDENTITY: Final[frozenset[str]] = frozenset()

# Neighbours kept per ROM. Enough to fill a "Similar games" shelf several times
# over and to give the personalised feed room to diversify, without letting the
# table grow to rom_count * library_size.
MAX_NEIGHBOURS: Final = 24

# Below this a "recommendation" is just two games that share the word Action.
MIN_EDGE_SCORE: Final = 0.05

# ROMs per write batch. Bounds peak memory and lets the task commit as it goes.
BUILD_BATCH_SIZE: Final = 500

# Neighbours from any one franchise allowed into the stored graph. Read-time
# diversity can only reorder what was stored, so without this a game deep in a
# big series has nothing but that series to promote.
MAX_STORED_PER_SERIES: Final = 6

# Neighbours buffered per ROM while the sweep runs. Deep enough that the
# filters in `_select_edges` can still fill MAX_NEIGHBOURS, shallow enough
# that a 50k library does not spend hundreds of MB holding it.
MAX_BUFFERED_NEIGHBOURS: Final = 64

# ROMs a top-up will score before it defers to a full rebuild instead. Past
# this the incremental path costs what a rebuild costs, and a rebuild also
# refreshes the IDF the rest of the graph is scored against.
MAX_TOP_UP_ROMS: Final = 5_000

# Existing ROMs whose stored neighbour lists a top-up rewrites, strongest new
# offer first. A game added to a large library brushes against thousands of
# neighbours but displaces a stored edge in very few of them.
MAX_TOP_UP_NEIGHBOURS: Final = 2_000


def _offer(buffer: list[tuple[float, int]], score: float, rom_id: int) -> None:
    """Keep the best MAX_BUFFERED_NEIGHBOURS offers in a min-heap."""
    if len(buffer) < MAX_BUFFERED_NEIGHBOURS:
        heapq.heappush(buffer, (score, rom_id))
    elif score > buffer[0][0]:
        heapq.heapreplace(buffer, (score, rom_id))


@dataclass
class BuildStats:
    roms_indexed: int = 0
    edges_written: int = 0
    roms_without_metadata: int = 0
    neighbours_updated: int = 0
    total: int = 0


@dataclass
class _PairSignals:
    """Sparse, symmetric side-signals keyed by an ordered ROM id pair."""

    igdb: dict[tuple[int, int], float] = field(default_factory=dict)
    co_play: dict[tuple[int, int], float] = field(default_factory=dict)
    co_collection: dict[tuple[int, int], float] = field(default_factory=dict)
    play_totals: dict[int, int] = field(default_factory=dict)
    collection_totals: dict[int, int] = field(default_factory=dict)

    # ROM id -> every ROM linked to it by a non-content signal. Built once
    # after collection: deriving it per ROM would rescan all three pair maps
    # for every ROM in the library.
    adjacency: defaultdict[int, set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )

    def index_adjacency(self) -> None:
        for source in (self.igdb, self.co_play, self.co_collection):
            for left, right in source:
                self.adjacency[left].add(right)
                self.adjacency[right].add(left)

    def partners_of(self, rom_id: int) -> set[int]:
        return self.adjacency.get(rom_id, set())


@dataclass(frozen=True)
class _GraphInputs:
    """One library snapshot, and everything a scoring sweep derives from it."""

    features: dict[int, RomFeatures]
    vectors: dict[int, dict[str, float]]
    postings: dict[str, list[int]]
    signals: _PairSignals
    identities: Mapping[int, frozenset[str]]

    @property
    def total_documents(self) -> int:
        return len(self.features)


# Offers waiting to become edges, keyed by the ROM they belong to.
_Buffers = defaultdict[int, list[tuple[float, int]]]


def _series_tokens(feature: RomFeatures) -> set[str]:
    """Every franchise a game carries; keying on one splits a series in two."""
    return {token for token in feature.tokens if token_facet(token) == Facet.FRANCHISE}


def _pair_key(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left < right else (right, left)


class SimilarityBuilder:
    """Assembles the similarity graph and writes it to `rom_similarity`."""

    def __init__(self, progress: Callable[[BuildStats], None] | None = None) -> None:
        self._progress = progress
        self.stats = BuildStats()

    def build(self) -> BuildStats:
        """Rescore the whole library, replacing every ROM's edges."""
        inputs = self._prepare()
        if inputs is None:
            return self.stats

        log.info(f"Scoring similarity for {inputs.total_documents} ROMs")
        self._score_and_write(inputs, sorted(inputs.features))

        log.info(
            f"Recommendations index built: {self.stats.roms_indexed} ROMs, "
            f"{self.stats.edges_written} edges"
        )
        return self.stats

    def build_for(self, rom_ids: Collection[int]) -> BuildStats:
        """Score `rom_ids` against the library, leaving the rest of the graph alone.

        The ROMs they match keep their stored neighbours and gain the new ones,
        rather than being rescored, so a game is reachable from both directions
        without paying for the all-pairs sweep. Mixing the two snapshots is
        sound because the stored scores are at most one rebuild old; the
        nightly build is what makes the whole graph exact again.
        """
        if not rom_ids:
            return self.stats

        inputs = self._prepare()
        if inputs is None:
            return self.stats

        requested = set(rom_ids)
        targets = sorted(requested & inputs.features.keys())
        # Overwritten rather than added to: `_prepare` counted the whole library.
        self.stats.roms_without_metadata = len(requested) - len(targets)
        self.stats.total = len(targets)
        self._report()

        if not targets:
            return self.stats

        log.info(f"Scoring similarity for {len(targets)} ROMs against the library")
        buffers = self._score_and_write(inputs, targets)
        self._merge_neighbour_edges(inputs, buffers, rescored=set(targets))

        log.info(
            f"Recommendations index topped up: {self.stats.roms_indexed} ROMs, "
            f"{self.stats.neighbours_updated} neighbours, "
            f"{self.stats.edges_written} edges"
        )
        return self.stats

    # --- Inputs ------------------------------------------------------------------

    def _prepare(self) -> _GraphInputs | None:
        """Read the library once and derive everything the scoring needs."""
        feature_rows = db_recommendation_handler.get_feature_rows()
        if not feature_rows:
            log.info("No ROMs to index for recommendations")
            return None

        features = self._build_features(feature_rows)
        self.stats.total = len(features)
        self._report()

        total_documents = len(features)
        idf = compute_idf(
            (feature.tokens for feature in features.values()), total_documents
        )
        vectors = build_normalised_vectors(
            {rom_id: feature.tokens for rom_id, feature in features.items()}, idf
        )
        postings = build_inverted_index(features)

        # Resolving an IGDB id back to a ROM is one-to-many; any owned copy of
        # the game is an equally good target for the edge.
        igdb_to_rom = {
            igdb_id: rom_id
            for rom_id, igdb_id in db_recommendation_handler.get_rom_igdb_ids().items()
            if rom_id in features
        }
        identities = {
            rom_id: tokens
            for rom_id, tokens in db_recommendation_handler.get_rom_identity_ids().items()
            if rom_id in features
        }
        signals = self._collect_pair_signals(features, identities, igdb_to_rom)

        return _GraphInputs(
            features=features,
            vectors=vectors,
            postings=postings,
            signals=signals,
            identities=identities,
        )

    def _build_features(self, rows: Sequence[RomFeatureRow]) -> dict[int, RomFeatures]:
        features: dict[int, RomFeatures] = {}

        for row in rows:
            tokens = extract_tokens(
                platform_id=row.platform_id,
                genres=row.genres,
                franchises=row.franchises,
                collections=row.collections,
                companies=row.companies,
                developers=row.developers,
                publishers=row.publishers,
                game_modes=row.game_modes,
                keywords=row.keywords,
                themes=row.themes,
                player_perspectives=row.player_perspectives,
                first_release_date=row.first_release_date,
            )

            if not has_taste_signal(tokens):
                self.stats.roms_without_metadata += 1
                continue

            features[row.rom_id] = RomFeatures(
                rom_id=row.rom_id,
                platform_id=row.platform_id,
                tokens=tokens,
                average_rating=row.average_rating,
                title_key=row.title_key,
            )

        return features

    def _collect_pair_signals(
        self,
        features: dict[int, RomFeatures],
        identities: Mapping[int, frozenset[str]],
        igdb_to_rom: dict[int, int],
    ) -> _PairSignals:
        signals = _PairSignals()

        for rom_id, related_igdb_ids in db_recommendation_handler.iter_igdb_related():
            if rom_id not in features:
                continue
            for related_igdb_id in related_igdb_ids:
                related_rom_id = igdb_to_rom.get(related_igdb_id)
                # IGDB's list is mostly games the user does not own; only the
                # ones actually on the shelf are worth an edge.
                if related_rom_id is None or related_rom_id == rom_id:
                    continue
                if self._is_duplicate(rom_id, related_rom_id, identities):
                    continue
                signals.igdb[_pair_key(rom_id, related_rom_id)] = 1.0

        self._count_co_occurrence(
            db_recommendation_handler.get_played_sets(),
            features,
            identities,
            signals.co_play,
            signals.play_totals,
        )
        self._count_co_occurrence(
            db_recommendation_handler.get_collection_membership_sets(),
            features,
            identities,
            signals.co_collection,
            signals.collection_totals,
        )

        signals.index_adjacency()

        log.debug(
            f"Pair signals: igdb={len(signals.igdb)}, "
            f"co_play={len(signals.co_play)}, "
            f"co_collection={len(signals.co_collection)}"
        )
        return signals

    def _count_co_occurrence(
        self,
        id_sets: Iterable[Sequence[int]],
        features: dict[int, RomFeatures],
        identities: Mapping[int, frozenset[str]],
        pair_counts: dict[tuple[int, int], float],
        totals: dict[int, int],
    ) -> None:
        raw: defaultdict[tuple[int, int], int] = defaultdict(int)

        for id_set in id_sets:
            known = sorted({rom_id for rom_id in id_set if rom_id in features})
            if len(known) < 2:
                continue

            for rom_id in known:
                totals[rom_id] = totals.get(rom_id, 0) + 1

            for left, right in combinations(known, 2):
                if self._is_duplicate(left, right, identities):
                    continue
                raw[(left, right)] += 1

        for (left, right), count in raw.items():
            pair_counts[(left, right)] = normalise_co_occurrence(
                count, totals.get(left, 0), totals.get(right, 0)
            )

    @staticmethod
    def _is_duplicate(
        left: int, right: int, identities: Mapping[int, frozenset[str]]
    ) -> bool:
        """Files of one game (regions, revisions, storefronts) are not recommendations."""
        return not identities.get(left, _NO_IDENTITY).isdisjoint(
            identities.get(right, _NO_IDENTITY)
        )

    # --- Scoring -----------------------------------------------------------------

    def _score_and_write(
        self, inputs: _GraphInputs, targets: Sequence[int]
    ) -> _Buffers:
        """Rescore each target against the library and replace its edges.

        Returns the offers left over for ROMs outside `targets`, which a full
        build never has and a top-up folds into their stored neighbours.
        """
        batch_rom_ids: list[int] = []
        batch_edges: list[dict[str, Any]] = []

        # Ascending id order is what completes each buffer: once a target has
        # been swept, every pair it shares with another target has been scored,
        # so its neighbours are final and the buffer can be selected and freed.
        buffers: _Buffers = defaultdict(list)
        swept: set[int] = set()

        for rom_id in targets:
            self._score_rom(inputs, inputs.features[rom_id], swept, buffers)
            swept.add(rom_id)

            edges = self._select_edges(
                inputs, inputs.features[rom_id], buffers.pop(rom_id, [])
            )

            batch_rom_ids.append(rom_id)
            batch_edges.extend(edges)
            self.stats.roms_indexed += 1

            if len(batch_rom_ids) >= BUILD_BATCH_SIZE:
                self._flush(batch_rom_ids, batch_edges)
                batch_rom_ids, batch_edges = [], []

        self._flush(batch_rom_ids, batch_edges)
        return buffers

    def _score_rom(
        self,
        inputs: _GraphInputs,
        feature: RomFeatures,
        swept: set[int],
        buffers: _Buffers,
    ) -> None:
        """Score this ROM against its candidates, offering in both directions.

        Candidate generation is symmetric -- two ROMs sharing a token each find
        the other -- so an already swept candidate is skipped: scoring the pair
        from one side halves the dot products, which dominate the build, and
        scoring it from both would offer the same neighbour twice.
        """
        rom_id = feature.rom_id
        source_vector = inputs.vectors.get(rom_id, {})

        candidates = candidate_ids(feature, inputs.postings, inputs.total_documents)
        # A game IGDB relates to, or that users play alongside this one, is
        # worth scoring even when they share no metadata facet at all.
        candidates |= inputs.signals.partners_of(rom_id)

        for candidate_id in candidates:
            if candidate_id == rom_id or candidate_id in swept:
                continue
            if self._is_duplicate(rom_id, candidate_id, inputs.identities):
                continue

            content = content_similarity(
                source_vector, inputs.vectors.get(candidate_id, {})
            )
            key = _pair_key(rom_id, candidate_id)
            igdb_prior = inputs.signals.igdb.get(key, 0.0)
            co_play = inputs.signals.co_play.get(key, 0.0)
            co_collection = inputs.signals.co_collection.get(key, 0.0)

            # Only the target's quality bonus differs by direction, so the pair
            # is blended twice off the one content score.
            for source, target in ((rom_id, candidate_id), (candidate_id, rom_id)):
                score = blend(
                    content=content,
                    igdb_prior=igdb_prior,
                    co_play=co_play,
                    co_collection=co_collection,
                    average_rating=inputs.features[target].average_rating,
                )
                if score >= MIN_EDGE_SCORE:
                    _offer(buffers[source], score, target)

    def _merge_neighbour_edges(
        self,
        inputs: _GraphInputs,
        buffers: _Buffers,
        rescored: set[int],
    ) -> None:
        """Fold the ROMs a top-up scored into the neighbour lists of what they matched.

        Reselecting from stored offers plus new ones costs one read and one
        write per neighbour, where rescoring them would cost another sweep.
        """
        ranked = sorted(buffers, key=lambda rom_id: (-max(buffers[rom_id])[0], rom_id))
        if not ranked:
            return

        ranked = ranked[:MAX_TOP_UP_NEIGHBOURS]
        stored = db_recommendation_handler.get_stored_edges(ranked)

        batch_rom_ids: list[int] = []
        batch_edges: list[dict[str, Any]] = []

        for rom_id in ranked:
            merged = list(buffers[rom_id])
            offered = {related_id for _, related_id in merged}
            for score, related_id in stored.get(rom_id, ()):
                # An edge to a rescored ROM has just been recomputed, and one to
                # a ROM that has left the library has nothing left to hydrate.
                if related_id in offered or related_id in rescored:
                    continue
                if related_id in inputs.features:
                    _offer(merged, score, related_id)

            batch_rom_ids.append(rom_id)
            batch_edges.extend(
                self._select_edges(inputs, inputs.features[rom_id], merged)
            )
            self.stats.neighbours_updated += 1

            if len(batch_rom_ids) >= BUILD_BATCH_SIZE:
                self._flush(batch_rom_ids, batch_edges)
                batch_rom_ids, batch_edges = [], []

        self._flush(batch_rom_ids, batch_edges)

    def _select_edges(
        self,
        inputs: _GraphInputs,
        feature: RomFeatures,
        buffered: list[tuple[float, int]],
    ) -> list[dict[str, Any]]:
        """Take the best buffered neighbours, dropping ones that duplicate each other.

        `_is_duplicate` only compares a candidate against the source, so
        without this two discs of one release would each take a slot.
        """
        rom_id = feature.rom_id
        source_vector = inputs.vectors.get(rom_id, {})

        edges: list[dict[str, Any]] = []
        taken_identities: set[str] = set()
        taken_titles: set[str] = set()
        series_counts: dict[str, int] = {}
        source_title = feature.title_key

        for score, candidate_id in sorted(
            buffered, key=lambda item: (-item[0], item[1])
        ):
            candidate_identity = inputs.identities.get(candidate_id, _NO_IDENTITY)
            if not candidate_identity.isdisjoint(taken_identities):
                continue
            taken_identities |= candidate_identity

            # IGDB gives every port its own id, so the identity check above
            # cannot catch the same game on other hardware. Ports collide with
            # each other as readily as with the source, hence both comparisons.
            candidate_title = inputs.features[candidate_id].title_key
            if candidate_title:
                if candidate_title == source_title or candidate_title in taken_titles:
                    continue
                taken_titles.add(candidate_title)

            series = _series_tokens(inputs.features[candidate_id])
            if series and any(
                series_counts.get(token, 0) >= MAX_STORED_PER_SERIES for token in series
            ):
                continue
            for token in series:
                series_counts[token] = series_counts.get(token, 0) + 1

            reasons = shared_reasons(
                source_vector, inputs.vectors.get(candidate_id, {})
            )
            if _pair_key(rom_id, candidate_id) in inputs.signals.igdb:
                reasons.append({"facet": Facet.IGDB, "value": "similar"})

            edges.append(
                {
                    "rom_id": rom_id,
                    "related_rom_id": candidate_id,
                    "score": round(score, 6),
                    "reasons": reasons,
                }
            )
            if len(edges) >= MAX_NEIGHBOURS:
                break

        return edges

    def _flush(self, rom_ids: list[int], edges: list[dict[str, Any]]) -> None:
        if not rom_ids:
            return

        self.stats.edges_written += db_recommendation_handler.replace_similarity_edges(
            rom_ids, edges
        )
        self._report()

    def _report(self) -> None:
        if self._progress:
            self._progress(self.stats)


def top_up_similarity(rom_ids: Collection[int]) -> None:
    """Give freshly scanned ROMs their edges without waiting for the nightly build.

    Runs inline for the ordinary case of a scan that touched part of a library.
    A scan that touched most of one is handed to the rebuild task instead, both
    because the incremental path saves nothing at that size and because the
    caller should not block on it.
    """
    unique_ids = set(rom_ids)
    if not unique_ids:
        return

    if len(unique_ids) > MAX_TOP_UP_ROMS:
        # Deferred: the task registry imports every task module, and one of
        # them imports this package.
        from tasks.registry import enqueue_task

        log.info(
            f"{len(unique_ids)} ROMs scanned, more than a recommendations top-up "
            "is worth; queueing a full rebuild instead"
        )
        enqueue_task("build_recommendations", task_kwargs={"force": True})
        return

    stats = SimilarityBuilder().build_for(unique_ids)
    if stats.roms_indexed:
        # Every cached ranking was computed against the graph this just moved.
        invalidate_all_cached_feeds()
