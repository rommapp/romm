"""Pure scoring primitives for the recommendation engine.

Deliberately free of ORM and I/O so the ranking maths can be exercised
directly in tests. Everything here operates on plain dataclasses and dicts.

The engine is library-relative: a facet is only as informative as it is rare
*in this library*. A shelf of 4000 arcade games learns that "Action" says
nothing and that "Metroidvania" says a great deal, without anyone tuning it.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

# Relative pull of each facet before IDF weighting. A shared series or
# franchise is far stronger evidence of "you will like this too" than a shared
# genre, and platform/decade are context rather than taste.
FACET_WEIGHTS: Final[Mapping[str, float]] = {
    "collection": 3.0,
    "franchise": 2.5,
    "genre": 1.0,
    # Below genre on purpose. A publisher spans wildly different games -- the
    # same Nintendo label covers Metroid, Tetris and Mario Kart -- so a shared
    # company is weaker evidence than a shared genre, not stronger.
    "company": 0.7,
    # Nearly every game is "Single player", so this mostly rides along; IDF
    # already flattens it and the low weight keeps it from breaking ties.
    "game_mode": 0.4,
    "platform": 0.4,
    "decade": 0.3,
}

# Facets present on more than this share of the library describe the library,
# not the game. They still contribute to the score (with a tiny IDF) but are
# skipped when generating candidates, so "Action" never expands into a
# postings list covering most of the shelf.
MAX_CANDIDATE_DF_RATIO: Final = 0.20
MAX_CANDIDATE_POSTINGS: Final = 2_000
# ...but the ratio only makes sense once there is a library to take a ratio of.
# Below this, expanding every token is cheap, and skipping them would leave a
# small shelf with no candidates at all.
MIN_CANDIDATE_DF: Final = 50

# Blend of the four independent signals. These sum to 1.0 so a raw score is
# readable as "fraction of maximum possible relatedness".
CONTENT_WEIGHT: Final = 0.55
IGDB_PRIOR_WEIGHT: Final = 0.20
CO_PLAY_WEIGHT: Final = 0.15
CO_COLLECTION_WEIGHT: Final = 0.10

# Similar *and* worth playing: a small nudge from critic rating, capped low
# enough that it reorders ties without overriding genuine relatedness.
MAX_QUALITY_BONUS: Final = 0.05

# Release proximity matters, but only softly: a decade token already carries
# most of the era signal.
SAME_DECADE_TOKEN: Final = "decade"


# Facets that describe the game itself rather than where it sits on the shelf.
# A ROM carrying none of these has nothing to be similar *about*: platform and
# decade alone would make every unmatched file in a folder a perfect match for
# every other, since both vectors normalise to the same thing.
TASTE_FACETS: Final[frozenset[str]] = frozenset(
    {"genre", "franchise", "collection", "company", "game_mode"}
)


def has_taste_signal(tokens: Sequence[str]) -> bool:
    """Whether a ROM carries any facet worth computing similarity from."""
    return any(token_facet(token) in TASTE_FACETS for token in tokens)


def make_token(facet: str, value: str) -> str:
    """Namespace a facet value so genre:Action never collides with tag:Action."""
    return f"{facet}:{value}"


def token_facet(token: str) -> str:
    return token.split(":", 1)[0]


def token_value(token: str) -> str:
    return token.split(":", 1)[1] if ":" in token else token


@dataclass(slots=True)
class RomFeatures:
    """Everything the scorer needs about one ROM."""

    rom_id: int
    platform_id: int
    tokens: tuple[str, ...] = ()
    average_rating: float | None = None


@dataclass(slots=True)
class ScoredNeighbour:
    """One edge of the item-item graph, with its explanation."""

    rom_id: int
    score: float
    reasons: list[dict[str, str]] = field(default_factory=list)


def extract_tokens(
    *,
    platform_id: int,
    genres: Sequence[str] | None = None,
    franchises: Sequence[str] | None = None,
    collections: Sequence[str] | None = None,
    companies: Sequence[str] | None = None,
    game_modes: Sequence[str] | None = None,
    first_release_date: int | None = None,
) -> tuple[str, ...]:
    """Flatten a ROM's metadata into namespaced, deduplicated feature tokens."""
    tokens: list[str] = []

    for facet, values in (
        ("genre", genres),
        ("franchise", franchises),
        ("collection", collections),
        ("company", companies),
        ("game_mode", game_modes),
    ):
        for value in values or ():
            cleaned = (value or "").strip()
            if cleaned:
                tokens.append(make_token(facet, cleaned))

    tokens.append(make_token("platform", str(platform_id)))

    year = release_year_from_epoch(first_release_date)
    if year is not None:
        tokens.append(make_token(SAME_DECADE_TOKEN, str(year // 10 * 10)))

    # dict.fromkeys keeps first-seen order, which keeps reasons deterministic.
    return tuple(dict.fromkeys(tokens))


def release_year_from_epoch(first_release_date: int | None) -> int | None:
    """Metadata stores release dates as a UTC epoch in seconds."""
    if not first_release_date:
        return None
    try:
        # Guard against the occasional millisecond value from a bad provider row.
        seconds = (
            first_release_date // 1000
            if abs(first_release_date) > 10_000_000_000
            else first_release_date
        )
        return 1970 + int(seconds // 31_556_952)
    except (TypeError, ValueError, OverflowError):
        return None


def compute_idf(
    documents: Iterable[Sequence[str]], total_documents: int
) -> dict[str, float]:
    """Inverse document frequency over the library's token vocabulary.

    Uses the BM25 form, ``ln(1 + (N - df + 0.5) / (df + 0.5))``. The simpler
    ``ln(1 + N / (1 + df))`` was tried first and discriminates far too weakly:
    a token on every ROM still scored ~0.69 against ~1.9 for a rare one, so
    "Single player" (present on nearly every game) kept enough weight to pull
    unrelated titles above genuine genre matches. BM25 drives the universal
    token to ~0.02 while leaving the rare one untouched, and stays positive on
    tiny libraries where a plain ``ln(N / df)`` collapses every token to zero.
    """
    if total_documents <= 0:
        return {}

    document_frequency: Counter[str] = Counter()
    for tokens in documents:
        document_frequency.update(set(tokens))

    return {
        token: math.log(1 + (total_documents - df + 0.5) / (df + 0.5))
        for token, df in document_frequency.items()
    }


def build_vector(tokens: Sequence[str], idf: Mapping[str, float]) -> dict[str, float]:
    """L2-normalised sparse vector, so cosine is a plain dot product.

    Normalising also stops metadata-rich ROMs from dominating every candidate
    list purely by carrying more tokens than everything else.
    """
    raw = {
        token: FACET_WEIGHTS.get(token_facet(token), 1.0) * idf.get(token, 0.0)
        for token in tokens
    }
    raw = {token: weight for token, weight in raw.items() if weight > 0}

    norm = math.sqrt(sum(weight * weight for weight in raw.values()))
    if norm == 0:
        return {}

    return {token: weight / norm for token, weight in raw.items()}


def content_similarity(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    """Cosine similarity of two normalised vectors."""
    # Iterate the smaller side; token overlap is sparse.
    if len(left) > len(right):
        left, right = right, left
    return sum(
        weight * right[token] for token, weight in left.items() if token in right
    )


def shared_reasons(
    left: Mapping[str, float],
    right: Mapping[str, float],
    *,
    limit: int = 3,
) -> list[dict[str, str]]:
    """The facets that actually drove the score, strongest first.

    These are what the UI renders as "Same series as Super Metroid" rather
    than an unexplained list of covers.
    """
    contributions = [
        (weight * right[token], token)
        for token, weight in left.items()
        if token in right
    ]
    contributions.sort(key=lambda pair: (-pair[0], pair[1]))

    reasons: list[dict[str, str]] = []
    seen_facets: set[str] = set()
    for _, token in contributions:
        facet = token_facet(token)
        # One reason per facet: three shared genres reads worse than a genre,
        # a company and a decade.
        if facet in seen_facets or facet == "platform":
            continue
        seen_facets.add(facet)
        reasons.append({"facet": facet, "value": token_value(token)})
        if len(reasons) >= limit:
            break

    return reasons


def quality_bonus(average_rating: float | None) -> float:
    """Map a 0-100 critic rating onto a small additive bonus."""
    if not average_rating:
        return 0.0
    normalised = max(0.0, min(1.0, average_rating / 100.0))
    return MAX_QUALITY_BONUS * normalised


def blend(
    *,
    content: float,
    igdb_prior: float = 0.0,
    co_play: float = 0.0,
    co_collection: float = 0.0,
    average_rating: float | None = None,
) -> float:
    """Combine the independent signals into a single 0-1-ish score."""
    return (
        CONTENT_WEIGHT * content
        + IGDB_PRIOR_WEIGHT * _clamp(igdb_prior)
        + CO_PLAY_WEIGHT * _clamp(co_play)
        + CO_COLLECTION_WEIGHT * _clamp(co_collection)
        + quality_bonus(average_rating)
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def build_inverted_index(
    features: Mapping[int, RomFeatures],
) -> dict[str, list[int]]:
    """Token -> ROM ids, used to avoid the O(n^2) all-pairs comparison.

    Only ROMs sharing at least one *discriminative* token are ever scored
    against each other, which is what keeps a 50k-ROM library tractable.
    """
    postings: dict[str, list[int]] = defaultdict(list)
    for rom_id, feature in features.items():
        for token in feature.tokens:
            postings[token].append(rom_id)
    return dict(postings)


def candidate_ids(
    feature: RomFeatures,
    postings: Mapping[str, Sequence[int]],
    total_documents: int,
) -> set[int]:
    """Candidate neighbours for one ROM, drawn from its rarest facets."""
    df_cap = max(MIN_CANDIDATE_DF, int(total_documents * MAX_CANDIDATE_DF_RATIO))
    candidates: set[int] = set()

    for token in feature.tokens:
        bucket = postings.get(token)
        if not bucket:
            continue
        if len(bucket) > df_cap or len(bucket) > MAX_CANDIDATE_POSTINGS:
            continue
        candidates.update(bucket)

    candidates.discard(feature.rom_id)
    return candidates


def normalise_co_occurrence(
    pair_count: float, left_total: int, right_total: int
) -> float:
    """Cosine-style normalisation of a raw co-occurrence count.

    Without this, whatever ROM sits in the most collections (or has the most
    play sessions) would look related to everything.
    """
    if pair_count <= 0 or left_total <= 0 or right_total <= 0:
        return 0.0
    return min(1.0, pair_count / math.sqrt(left_total * right_total))
