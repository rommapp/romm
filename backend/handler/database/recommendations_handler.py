from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import batched
from typing import Any, NamedTuple

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from decorators.database import begin_session
from models.collection import CollectionRom
from models.play_session import PlaySession
from models.recommendation import RomSimilarity
from models.rom import IDENTITY_ID_FIELDS, Rom, RomFacets, RomMetadata, RomUser

from .base_handler import DBBaseHandler

# Streaming chunk for the wide `roms` scan that reads the IGDB metadata blobs.
IGDB_SCAN_CHUNK_SIZE = 500

# Rows per INSERT when rewriting the similarity table.
EDGE_INSERT_CHUNK_SIZE = 1_000

# Co-occurrence sets larger than this say more about the collector than the
# games: a 900-ROM "Everything" collection would otherwise emit 400k pairs and
# relate its entire contents to itself.
MAX_CO_OCCURRENCE_SET_SIZE = 250

# Two ROMs sharing any of these are one title and are never recommended for
# each other. Read off the list `sibling_roms` matches on, but not scoped to a
# platform: a game reissued on other hardware is no more a suggestion either.
IDENTITY_ID_COLUMNS = tuple(getattr(RomFacets, field) for field in IDENTITY_ID_FIELDS)

# Votes a rating needs before it is trusted on its own in the cold-start feed;
# below this it is blended with the library mean.
BAYESIAN_PRIOR_VOTES = 50


class RomFeatureRow(NamedTuple):
    """The narrow slice of metadata the similarity build reads per ROM."""

    rom_id: int
    platform_id: int
    title_key: str | None
    genres: list[str] | None
    franchises: list[str] | None
    collections: list[str] | None
    companies: list[str] | None
    developers: list[str] | None
    publishers: list[str] | None
    game_modes: list[str] | None
    keywords: list[str] | None
    themes: list[str] | None
    player_perspectives: list[str] | None
    first_release_date: int | None
    average_rating: float | None


class UserAffinityRow(NamedTuple):
    """One ROM the user has engaged with, and how strongly."""

    rom_id: int
    rating: int | None
    status: str | None
    last_played: Any | None
    now_playing: bool
    hidden: bool
    playtime_ms: int


class SimilarRomEdge(NamedTuple):
    rom_id: int
    score: float
    reasons: list[dict[str, Any]]


class DBRecommendationsHandler(DBBaseHandler):
    # --- Similarity build inputs -------------------------------------------------

    @begin_session
    def get_feature_rows(
        self, session: Session = None  # type: ignore
    ) -> list[RomFeatureRow]:
        """Every ROM's facet values, for building the library-wide IDF.

        Reads `roms_facets` rather than `roms`: the values are mirrored there
        so aggregations never touch the wide provider-metadata blobs.
        """
        stmt = (
            select(
                RomFacets.rom_id,
                RomFacets.platform_id,
                Rom.name_sort_key,
                RomFacets.genres,
                RomFacets.franchises,
                RomFacets.collections,
                RomFacets.companies,
                RomFacets.developers,
                RomFacets.publishers,
                RomFacets.game_modes,
                RomFacets.keywords,
                RomFacets.themes,
                RomFacets.player_perspectives,
                Rom.generated_first_release_date,
                Rom.generated_average_rating,
            )
            .join(Rom, Rom.id == RomFacets.rom_id)
            .where(Rom.missing_from_fs.is_(False))
        )

        return [RomFeatureRow(*row) for row in session.execute(stmt).all()]

    @begin_session
    def get_rom_igdb_ids(
        self, session: Session = None  # type: ignore
    ) -> dict[int, int]:
        """ROM id -> IGDB id, for resolving IGDB's related-game ids to owned copies."""
        stmt = select(RomFacets.rom_id, RomFacets.igdb_id).where(
            RomFacets.igdb_id.is_not(None)
        )
        return {rom_id: igdb_id for rom_id, igdb_id in session.execute(stmt).all()}

    @begin_session
    def get_rom_identity_ids(
        self, session: Session = None  # type: ignore
    ) -> dict[int, frozenset[str]]:
        """ROM id -> "provider:id" tokens from every provider that matched it.

        Keyed by ROM id because the relationship is many-to-one: keying the
        other way drops every duplicate but one, which is the set duplicate
        suppression needs to see. Unmatched ROMs are absent.
        """
        stmt = select(RomFacets.rom_id, *IDENTITY_ID_COLUMNS)
        identities: dict[int, frozenset[str]] = {}
        for rom_id, *provider_ids in session.execute(stmt).all():
            tokens = frozenset(
                f"{column.key}:{provider_id}"
                for column, provider_id in zip(
                    IDENTITY_ID_COLUMNS, provider_ids, strict=True
                )
                if provider_id is not None
            )
            if tokens:
                identities[rom_id] = tokens
        return identities

    @begin_session
    def iter_igdb_related(
        self, session: Session = None  # type: ignore
    ) -> Iterator[tuple[int, list[int]]]:
        """Stream each ROM's IGDB related-game ids out of its metadata blob.

        Yields in chunks because this is the one query that has to read the
        wide `roms` row; everything else in the build works off narrow tables.
        """
        stmt = (
            select(Rom.id, Rom.igdb_metadata)
            .where(Rom.igdb_id.is_not(None), Rom.missing_from_fs.is_(False))
            .execution_options(yield_per=IGDB_SCAN_CHUNK_SIZE)
        )

        for rom_id, metadata in session.execute(stmt):
            if not metadata:
                continue

            related_ids: list[int] = []
            # `ports` is deliberately absent: a faithful port is a duplicate,
            # and a rebuilt one earns its place on its own facets.
            for bucket in (
                "similar_games",
                "remakes",
                "remasters",
                "expanded_games",
                "expansions",
                "dlcs",
            ):
                for entry in metadata.get(bucket) or ():
                    entry_id = entry.get("id") if isinstance(entry, dict) else None
                    if isinstance(entry_id, int):
                        related_ids.append(entry_id)

            if related_ids:
                yield rom_id, related_ids

    @begin_session
    def get_collection_membership_sets(
        self, session: Session = None  # type: ignore
    ) -> list[list[int]]:
        """ROM ids grouped by user collection, for co-membership scoring."""
        stmt = select(CollectionRom.collection_id, CollectionRom.rom_id).order_by(
            CollectionRom.collection_id
        )
        return self._group_second_by_first(session.execute(stmt).all())

    @begin_session
    def get_played_sets(
        self, session: Session = None  # type: ignore
    ) -> list[list[int]]:
        """ROM ids grouped by user, restricted to games they actually played.

        This is the item-based collaborative signal. On a single-user server it
        degrades gracefully into "things I play together" rather than vanishing.
        """
        stmt = (
            select(RomUser.user_id, RomUser.rom_id)
            .where(RomUser.last_played.is_not(None))
            .order_by(RomUser.user_id)
        )
        return self._group_second_by_first(session.execute(stmt).all())

    @staticmethod
    def _group_second_by_first(rows: Sequence[Any]) -> list[list[int]]:
        """Bucket (key, rom_id) rows into per-key id lists, dropping the noisy ones.

        Singletons carry no pair information and oversized sets carry mostly
        noise, so neither is worth handing to the pair counter.
        """
        grouped: dict[int, list[int]] = {}
        for key, rom_id in rows:
            grouped.setdefault(key, []).append(rom_id)

        return [
            ids
            for ids in grouped.values()
            if 1 < len(ids) <= MAX_CO_OCCURRENCE_SET_SIZE
        ]

    # --- Similarity build output -------------------------------------------------

    @begin_session
    def replace_similarity_edges(
        self,
        rom_ids: Sequence[int],
        edges: Sequence[dict[str, Any]],
        session: Session = None,  # type: ignore
    ) -> int:
        """Swap in a batch of ROMs' edges.

        Scoped to `rom_ids` rather than truncating the table so the build can
        commit incrementally: a task that dies halfway leaves stale edges for
        the ROMs it never reached, not an empty recommendations table.
        """
        if not rom_ids:
            return 0

        session.execute(delete(RomSimilarity).where(RomSimilarity.rom_id.in_(rom_ids)))

        written = 0
        for chunk in batched(edges, EDGE_INSERT_CHUNK_SIZE, strict=False):
            session.execute(insert(RomSimilarity), list(chunk))
            written += len(chunk)

        return written

    @begin_session
    def get_stored_edges(
        self,
        rom_ids: Sequence[int],
        session: Session = None,  # type: ignore
    ) -> dict[int, list[tuple[float, int]]]:
        """Each ROM's current neighbours, for a top-up to merge new ones into.

        Scores only: the reasons are recomputed against the live snapshot, so
        carrying the stored ones over would only preserve staler wording.
        """
        if not rom_ids:
            return {}

        stmt = select(
            RomSimilarity.rom_id, RomSimilarity.score, RomSimilarity.related_rom_id
        ).where(RomSimilarity.rom_id.in_(rom_ids))

        stored: dict[int, list[tuple[float, int]]] = {}
        for rom_id, score, related_rom_id in session.execute(stmt):
            stored.setdefault(rom_id, []).append((score, related_rom_id))
        return stored

    @begin_session
    def count_similarity_edges(self, session: Session = None) -> int:  # type: ignore
        return session.scalar(select(func.count()).select_from(RomSimilarity)) or 0

    # --- Reads -------------------------------------------------------------------

    @begin_session
    def get_similar_rom_edges(
        self,
        rom_id: int,
        limit: int = 20,
        session: Session = None,  # type: ignore
    ) -> list[SimilarRomEdge]:
        """Top precomputed neighbours of one ROM, best first.

        Returns ids rather than ROMs so every caller hydrates through the same
        `SimpleRomSchema` load path instead of each growing its own.
        """
        stmt = (
            select(
                RomSimilarity.related_rom_id,
                RomSimilarity.score,
                RomSimilarity.reasons,
            )
            .where(RomSimilarity.rom_id == rom_id)
            .order_by(RomSimilarity.score.desc(), RomSimilarity.related_rom_id.asc())
            .limit(limit)
        )

        return [
            SimilarRomEdge(rom_id=related_id, score=score, reasons=reasons or [])
            for related_id, score, reasons in session.execute(stmt).all()
        ]

    @begin_session
    def get_neighbours_for_roms(
        self,
        rom_ids: Sequence[int],
        limit_per_rom: int = 20,
        session: Session = None,  # type: ignore
    ) -> list[tuple[int, int, float, list[dict[str, Any]]]]:
        """Edges fanning out from a set of seed ROMs, for the personalised feed.

        Returns raw (seed_rom_id, related_rom_id, score, reasons) tuples; the
        ranking handler hydrates only the ROMs that survive its cut.
        """
        if not rom_ids:
            return []

        stmt = (
            select(
                RomSimilarity.rom_id,
                RomSimilarity.related_rom_id,
                RomSimilarity.score,
                RomSimilarity.reasons,
            )
            .where(RomSimilarity.rom_id.in_(rom_ids))
            .order_by(RomSimilarity.rom_id, RomSimilarity.score.desc())
        )

        # Trim per seed in Python: a per-group LIMIT needs a window function,
        # and the row counts here are already bounded by the build's top-N cut.
        per_seed: dict[int, int] = {}
        results: list[tuple[int, int, float, list[dict[str, Any]]]] = []
        for seed_id, related_id, score, reasons in session.execute(stmt):
            taken = per_seed.get(seed_id, 0)
            if taken >= limit_per_rom:
                continue
            per_seed[seed_id] = taken + 1
            results.append((seed_id, related_id, score, reasons or []))

        return results

    @begin_session
    def get_user_affinity(
        self,
        user_id: int,
        session: Session = None,  # type: ignore
    ) -> list[UserAffinityRow]:
        """Everything the user has done with each ROM, plus total playtime.

        Playtime comes from `play_sessions` (the accurate signal) while the
        rest comes from `rom_user`; a ROM can appear with either or both.
        """
        playtime_subq = (
            select(
                PlaySession.rom_id.label("rom_id"),
                func.coalesce(func.sum(PlaySession.duration_ms), 0).label(
                    "playtime_ms"
                ),
            )
            .where(PlaySession.user_id == user_id, PlaySession.rom_id.is_not(None))
            .group_by(PlaySession.rom_id)
            .subquery()
        )

        stmt = (
            select(
                RomUser.rom_id,
                RomUser.rating,
                RomUser.status,
                RomUser.last_played,
                RomUser.now_playing,
                RomUser.hidden,
                func.coalesce(playtime_subq.c.playtime_ms, 0),
            )
            .outerjoin(playtime_subq, playtime_subq.c.rom_id == RomUser.rom_id)
            .where(RomUser.user_id == user_id)
        )

        return [
            UserAffinityRow(
                rom_id=row[0],
                rating=row[1],
                status=row[2].value if hasattr(row[2], "value") else row[2],
                last_played=row[3],
                now_playing=bool(row[4]),
                hidden=bool(row[5]),
                playtime_ms=int(row[6] or 0),
            )
            for row in session.execute(stmt).all()
        ]

    @begin_session
    def get_rom_names(
        self,
        rom_ids: Sequence[int],
        session: Session = None,  # type: ignore
    ) -> dict[int, str]:
        """Display names only, for the "Because you played X" attribution."""
        if not rom_ids:
            return {}

        stmt = select(Rom.id, Rom.name, Rom.fs_name).where(Rom.id.in_(rom_ids))
        return {
            rom_id: name or fs_name
            for rom_id, name, fs_name in session.execute(stmt).all()
        }

    @begin_session
    def get_fallback_rom_ids(
        self,
        limit: int,
        exclude_rom_ids: Sequence[int] = (),
        session: Session = None,  # type: ignore
    ) -> list[int]:
        """Cold-start feed: the best-reviewed games in the library.

        Ranked by a Bayesian average, so a rating backed by few votes is
        pulled toward the library mean and a lone provider's perfect score
        does not outrank a broadly-liked classic.
        """
        mean_rating = session.scalar(
            select(func.avg(RomMetadata.average_rating)).where(
                RomMetadata.average_rating.is_not(None)
            )
        )
        prior = float(mean_rating or 0.0)

        votes = func.coalesce(RomMetadata.rating_count, 0)
        # (v * R + m * C) / (v + m): the standard shrinkage estimator, with m
        # acting as "how many votes it takes to be believed on your own".
        bayesian = (
            votes * RomMetadata.average_rating + BAYESIAN_PRIOR_VOTES * prior
        ) / (votes + BAYESIAN_PRIOR_VOTES)

        stmt = (
            select(Rom.id)
            .join(RomMetadata, RomMetadata.rom_id == Rom.id)
            .where(
                Rom.missing_from_fs.is_(False),
                RomMetadata.average_rating.is_not(None),
            )
            .order_by(bayesian.desc(), Rom.name_sort_key.asc())
            .limit(limit)
        )

        if exclude_rom_ids:
            stmt = stmt.where(Rom.id.not_in(exclude_rom_ids))

        return list(session.execute(stmt).scalars().all())
