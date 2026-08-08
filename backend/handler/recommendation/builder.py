"""Builds the precomputed item-item similarity graph.

Run from the scheduled recommendations task. The whole graph is derived from
one consistent snapshot of the library, because the IDF weighting that makes
scores library-relative changes as the shelf grows.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Any, Final

from handler.database import db_recommendation_handler
from handler.database.recommendations_handler import RomFeatureRow
from logger.logger import log

from .scoring import (
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
)

# Neighbours kept per ROM. Enough to fill a "Similar games" shelf several times
# over and to give the personalised feed room to diversify, without letting the
# table grow to rom_count * library_size.
MAX_NEIGHBOURS: Final = 24

# Below this a "recommendation" is just two games that share the word Action.
MIN_EDGE_SCORE: Final = 0.05

# ROMs per write batch. Bounds peak memory and lets the task commit as it goes.
BUILD_BATCH_SIZE: Final = 500

# Neighbours from any one franchise allowed into the stored graph. Read-time
# diversity can only reorder what was stored, so a game sitting deep in a big
# series would otherwise have all 24 slots taken by that series and nothing
# left to promote.
MAX_STORED_PER_SERIES: Final = 6

# Hard ceiling on candidates scored per ROM. Reached only by games whose every
# facet is rare, where the tail is noise anyway.
MAX_CANDIDATES_PER_ROM: Final = 1_500


@dataclass
class BuildStats:
    roms_indexed: int = 0
    edges_written: int = 0
    roms_without_metadata: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


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


def _series_token(feature: RomFeatures) -> str | None:
    """The franchise token a game carries, used as its series key."""
    return next(
        (token for token in feature.tokens if token.startswith("franchise:")), None
    )


def _pair_key(left: int, right: int) -> tuple[int, int]:
    return (left, right) if left < right else (right, left)


class SimilarityBuilder:
    """Assembles the similarity graph and writes it to `rom_similarity`."""

    def __init__(self, progress: Callable[[BuildStats], None] | None = None) -> None:
        self._progress = progress
        self.stats = BuildStats()

    def build(self) -> BuildStats:
        feature_rows = db_recommendation_handler.get_feature_rows()
        if not feature_rows:
            log.info("No ROMs to index for recommendations")
            return self.stats

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

        igdb_ids = {
            rom_id: igdb_id
            for rom_id, igdb_id in db_recommendation_handler.get_rom_igdb_ids().items()
            if rom_id in features
        }
        # Resolving an IGDB id back to a ROM is one-to-many; any owned copy of
        # the game is an equally good target for the edge.
        igdb_to_rom = {igdb_id: rom_id for rom_id, igdb_id in igdb_ids.items()}
        signals = self._collect_pair_signals(features, igdb_ids, igdb_to_rom)

        log.info(f"Scoring similarity for {total_documents} ROMs")
        self._score_and_write(features, vectors, postings, signals, igdb_ids)

        log.info(
            f"Recommendations index built: {self.stats.roms_indexed} ROMs, "
            f"{self.stats.edges_written} edges"
        )
        return self.stats

    # --- Inputs ------------------------------------------------------------------

    def _build_features(self, rows: Sequence[RomFeatureRow]) -> dict[int, RomFeatures]:
        features: dict[int, RomFeatures] = {}

        for row in rows:
            tokens = extract_tokens(
                platform_id=row.platform_id,
                genres=row.genres,
                franchises=row.franchises,
                collections=row.collections,
                companies=row.companies,
                game_modes=row.game_modes,
                keywords=row.keywords,
                themes=row.themes,
                player_perspectives=row.player_perspectives,
                first_release_date=row.first_release_date,
            )

            # Platform and decade alone describe a shelf, not a game: two
            # unmatched files from the same folder would otherwise normalise to
            # identical vectors and score a perfect match against each other.
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
        igdb_ids: dict[int, int],
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
                if self._is_duplicate(rom_id, related_rom_id, igdb_ids):
                    continue
                signals.igdb[_pair_key(rom_id, related_rom_id)] = 1.0

        self._count_co_occurrence(
            db_recommendation_handler.get_played_sets(),
            features,
            igdb_ids,
            signals.co_play,
            signals.play_totals,
        )
        self._count_co_occurrence(
            db_recommendation_handler.get_collection_membership_sets(),
            features,
            igdb_ids,
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
        igdb_ids: dict[int, int],
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
                if self._is_duplicate(left, right, igdb_ids):
                    continue
                raw[(left, right)] += 1

        for (left, right), count in raw.items():
            pair_counts[(left, right)] = normalise_co_occurrence(
                count, totals.get(left, 0), totals.get(right, 0)
            )

    @staticmethod
    def _is_duplicate(left: int, right: int, igdb_ids: dict[int, int]) -> bool:
        """Two files of the same game (regions, revisions) are not a recommendation."""
        left_igdb = igdb_ids.get(left)
        return left_igdb is not None and left_igdb == igdb_ids.get(right)

    # --- Scoring -----------------------------------------------------------------

    def _score_and_write(
        self,
        features: dict[int, RomFeatures],
        vectors: dict[int, dict[str, float]],
        postings: dict[str, list[int]],
        signals: _PairSignals,
        igdb_ids: dict[int, int],
    ) -> None:
        total_documents = len(features)
        batch_rom_ids: list[int] = []
        batch_edges: list[dict[str, Any]] = []

        for rom_id, feature in features.items():
            edges = self._score_one(
                feature, features, vectors, postings, signals, igdb_ids, total_documents
            )

            batch_rom_ids.append(rom_id)
            batch_edges.extend(edges)
            self.stats.roms_indexed += 1

            if len(batch_rom_ids) >= BUILD_BATCH_SIZE:
                self._flush(batch_rom_ids, batch_edges)
                batch_rom_ids, batch_edges = [], []

        self._flush(batch_rom_ids, batch_edges)

    def _score_one(
        self,
        feature: RomFeatures,
        features: dict[int, RomFeatures],
        vectors: dict[int, dict[str, float]],
        postings: dict[str, list[int]],
        signals: _PairSignals,
        igdb_ids: dict[int, int],
        total_documents: int,
    ) -> list[dict[str, Any]]:
        rom_id = feature.rom_id
        source_vector = vectors.get(rom_id, {})

        candidates = candidate_ids(feature, postings, total_documents)
        # A game IGDB relates to, or that users play alongside this one, is
        # worth scoring even when they share no metadata facet at all.
        candidates |= signals.partners_of(rom_id)
        candidates.discard(rom_id)

        if len(candidates) > MAX_CANDIDATES_PER_ROM:
            candidates = set(
                sorted(
                    candidates,
                    key=lambda cid: content_similarity(
                        source_vector, vectors.get(cid, {})
                    ),
                    reverse=True,
                )[:MAX_CANDIDATES_PER_ROM]
            )

        scored: list[tuple[float, int, list[dict[str, str]]]] = []
        for candidate_id in candidates:
            if self._is_duplicate(rom_id, candidate_id, igdb_ids):
                continue

            candidate_vector = vectors.get(candidate_id, {})
            content = content_similarity(source_vector, candidate_vector)
            key = _pair_key(rom_id, candidate_id)

            score = blend(
                content=content,
                igdb_prior=signals.igdb.get(key, 0.0),
                co_play=signals.co_play.get(key, 0.0),
                co_collection=signals.co_collection.get(key, 0.0),
                average_rating=features[candidate_id].average_rating,
            )

            if score < MIN_EDGE_SCORE:
                continue

            reasons = shared_reasons(source_vector, candidate_vector)
            if key in signals.igdb:
                reasons.append({"facet": "igdb", "value": "similar"})

            scored.append((score, candidate_id, reasons))

        scored.sort(key=lambda item: (-item[0], item[1]))

        # Second pass, over the ranked list: drop neighbours that duplicate the
        # source or each other. The per-candidate check above only compares
        # against the source, so two discs of one release (same igdb_id, same
        # platform) would otherwise both take a slot.
        edges: list[dict[str, Any]] = []
        taken_igdb_ids: set[int] = set()
        series_counts: dict[str, int] = {}
        source_title = feature.title_key

        for score, candidate_id, reasons in scored:
            candidate_igdb_id = igdb_ids.get(candidate_id)
            if candidate_igdb_id is not None:
                if candidate_igdb_id in taken_igdb_ids:
                    continue
                taken_igdb_ids.add(candidate_igdb_id)

            # The same game on another platform is not a recommendation, and
            # IGDB gives ports their own id so the id check cannot catch it.
            candidate_title = features[candidate_id].title_key
            if source_title and candidate_title == source_title:
                continue

            series = _series_token(features[candidate_id])
            if series is not None:
                if series_counts.get(series, 0) >= MAX_STORED_PER_SERIES:
                    continue
                series_counts[series] = series_counts.get(series, 0) + 1

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
