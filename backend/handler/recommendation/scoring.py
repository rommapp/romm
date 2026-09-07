"""Pure scoring primitives for the recommendation engine.

Free of ORM and I/O so the ranking maths can be exercised directly in tests.
The engine is library-relative: a facet is only as informative as it is rare
*in this library*, so no shelf needs its weights tuned by hand.
"""

from __future__ import annotations

import enum
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final


class Facet(enum.StrEnum):
    """Every axis a recommendation can be explained by.

    Reaches the API as a similarity reason's `facet`, so a new member fails
    the frontend typecheck until the UI maps it.
    """

    COLLECTION = "collection"
    FRANCHISE = "franchise"
    GENRE = "genre"
    PERSPECTIVE = "perspective"
    THEME = "theme"
    KEYWORD = "keyword"
    DEVELOPER = "developer"
    PUBLISHER = "publisher"
    COMPANY = "company"
    GAME_MODE = "game_mode"
    PLATFORM = "platform"
    DECADE = "decade"

    # Not scored, and carry no value of their own: where the link came from
    # when it was not metadata overlap.
    IGDB = "igdb"
    TOP_RATED = "top_rated"


# Relative pull of each facet before IDF weighting. A shared series or
# franchise is far stronger evidence of "you will like this too" than a shared
# genre, and platform/decade are context rather than taste.
FACET_WEIGHTS: Final[Mapping[str, float]] = {
    Facet.COLLECTION: 3.0,
    Facet.FRANCHISE: 2.5,
    Facet.GENRE: 1.0,
    # IGDB's curated viewpoint list: "Side view" versus "First person" says
    # more about how a game plays than most genre labels do.
    Facet.PERSPECTIVE: 1.0,
    # A curated, low-cardinality second genre axis (Horror, Comedy, Fantasy).
    Facet.THEME: 0.9,
    # Community tags, high cardinality and mixed quality ("motorcycle" sits
    # beside "metroidvania"), so IDF does most of the work here.
    Facet.KEYWORD: 0.7,
    # Who actually made it. Results barely move across 0.4-1.0, since tight
    # studios share genre and theme with themselves anyway.
    Facet.DEVELOPER: 0.7,
    # Who shipped it. A label spans everything it ever released, and regional
    # distributors land here too, dense enough that IDF alone leaves them
    # saying more than they mean.
    Facet.PUBLISHER: 0.25,
    # Used only where no provider reported roles, so the value could be either.
    Facet.COMPANY: 0.7,
    # Nearly every game is "Single player", so this mostly rides along; IDF
    # already flattens it and the low weight keeps it from breaking ties.
    Facet.GAME_MODE: 0.4,
    Facet.PLATFORM: 0.4,
    Facet.DECADE: 0.3,
}

# Facets on more than this share of the library describe the library, not the
# game. They still score (with a tiny IDF) but are skipped when generating
# candidates, so "Action" never expands into most of the shelf.
MAX_CANDIDATE_DF_RATIO: Final = 0.20
MAX_CANDIDATE_POSTINGS: Final = 2_000
# Soft ceiling per ROM: the last posting list is taken whole, so the candidate
# set can overshoot by up to one bucket.
MAX_CANDIDATES_PER_ROM: Final = 1_500
# Floor under the ratio above, so a small shelf is not left with no candidates.
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

# Sightings a co-occurrence needs before it is taken at face value. One user
# playing two games makes them a perfect cosine match, and most servers have
# one user, so agreement is damped by the evidence behind it the same way a
# rating is by its vote count. A lone sighting keeps a quarter of its weight,
# which leaves it below MIN_EDGE_SCORE on its own.
CO_OCCURRENCE_PRIOR: Final = 3.0

# Length-normalisation strength: 1.0 is plain L2, 0.0 scales every vector by
# the library average instead of its own length. Zero because facet counts are
# not verbosity: a richly tagged game really does have more in common, and
# dividing by its own length punished it for being well documented.
PIVOT_B: Final = 0.0

# Facets that place a game on the shelf rather than describe it: two unmatched
# files in one folder would otherwise normalise to identical vectors.
CONTEXT_FACETS: Final[frozenset[str]] = frozenset({Facet.PLATFORM, Facet.DECADE})
TASTE_FACETS: Final[frozenset[str]] = frozenset(FACET_WEIGHTS) - CONTEXT_FACETS


def has_taste_signal(tokens: Sequence[str]) -> bool:
    """Whether a ROM carries any facet worth computing similarity from."""
    return any(token_facet(token) in TASTE_FACETS for token in tokens)


def make_token(facet: Facet, value: str) -> str:
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
    # Normalised title, used to spot the same game released on another
    # platform, which IGDB indexes as a separate id.
    title_key: str | None = None


def extract_tokens(
    *,
    platform_id: int,
    genres: Sequence[str] | None = None,
    franchises: Sequence[str] | None = None,
    collections: Sequence[str] | None = None,
    companies: Sequence[str] | None = None,
    developers: Sequence[str] | None = None,
    publishers: Sequence[str] | None = None,
    game_modes: Sequence[str] | None = None,
    keywords: Sequence[str] | None = None,
    themes: Sequence[str] | None = None,
    player_perspectives: Sequence[str] | None = None,
    first_release_date: int | None = None,
) -> tuple[str, ...]:
    """Flatten a ROM's metadata into namespaced, deduplicated feature tokens."""
    tokens: list[str] = []

    # Prefer the role-split lists where a provider reported them, and fall back
    # to the merged one otherwise. Emitting both would count an IGDB-matched
    # game's studio twice while a game matched elsewhere counted once.
    has_roles = bool(developers) or bool(publishers)
    company_facets: tuple[tuple[Facet, Sequence[str] | None], ...] = (
        ((Facet.DEVELOPER, developers), (Facet.PUBLISHER, publishers))
        if has_roles
        else ((Facet.COMPANY, companies),)
    )

    for facet, values in (
        (Facet.GENRE, genres),
        (Facet.FRANCHISE, franchises),
        (Facet.COLLECTION, collections),
        *company_facets,
        (Facet.GAME_MODE, game_modes),
        (Facet.KEYWORD, keywords),
        (Facet.THEME, themes),
        (Facet.PERSPECTIVE, player_perspectives),
    ):
        for value in values or ():
            cleaned = (value or "").strip()
            if cleaned:
                tokens.append(make_token(facet, cleaned))

    tokens.append(make_token(Facet.PLATFORM, str(platform_id)))

    year = release_year_from_epoch(first_release_date)
    if year is not None:
        tokens.append(make_token(Facet.DECADE, str(year // 10 * 10)))

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

    BM25's form, ``ln(1 + (N - df + 0.5) / (df + 0.5))``: it drives a token
    carried by every ROM to ~0.02 while leaving rare ones untouched, and stays
    positive on libraries too small for ``ln(N / df)`` to discriminate at all.
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
    """Raw facet-weighted IDF vector, before any length normalisation.

    A facet's weight is split across its values, so one franchise counts for
    more than one of six and a compilation does not match strongly on all six.
    Splitting by sqrt of the count keeps three genres worth more in total than
    one without letting them scale linearly.
    """
    facet_counts = Counter(token_facet(token) for token in tokens)

    raw = {
        token: (
            FACET_WEIGHTS.get(token_facet(token), 1.0)
            * idf.get(token, 0.0)
            / math.sqrt(facet_counts[token_facet(token)])
        )
        for token in tokens
    }
    return {token: weight for token, weight in raw.items() if weight > 0}


def vector_norm(vector: Mapping[str, float]) -> float:
    return math.sqrt(sum(weight * weight for weight in vector.values()))


def pivot_length(norm: float, average_norm: float, *, b: float = PIVOT_B) -> float:
    """Blend a vector's own length with the library average; see PIVOT_B."""
    if average_norm <= 0:
        return norm or 1.0
    return (1.0 - b) * average_norm + b * norm


def normalise(vector: Mapping[str, float], pivot: float) -> dict[str, float]:
    if pivot <= 0:
        return {}
    return {token: weight / pivot for token, weight in vector.items()}


def build_normalised_vectors(
    token_sets: Mapping[int, Sequence[str]], idf: Mapping[str, float]
) -> dict[int, dict[str, float]]:
    """Vectors for a whole library, pivot-normalised against its average length.

    Needs the full set up front: the pivot is library-relative, as the IDF is.
    """
    raw = {key: build_vector(tokens, idf) for key, tokens in token_sets.items()}
    norms = {key: vector_norm(vector) for key, vector in raw.items()}

    populated = [norm for norm in norms.values() if norm > 0]
    average_norm = sum(populated) / len(populated) if populated else 0.0

    return {
        key: normalise(vector, pivot_length(norms[key], average_norm))
        for key, vector in raw.items()
    }


def content_similarity(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    """Dot product of two pivot-normalised vectors."""
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
    # Keywords rank last whatever they contribute: they carry the highest IDF,
    # so they would otherwise explain two Castlevanias with "drawbridge". They
    # still earn a slot once the curated facets run out.
    contributions.sort(
        key=lambda pair: (token_facet(pair[1]) == Facet.KEYWORD, -pair[0], pair[1])
    )

    reasons: list[dict[str, str]] = []
    seen_facets: set[str] = set()
    for _, token in contributions:
        facet = token_facet(token)
        # One reason per facet: three shared genres reads worse than a genre,
        # a company and a decade.
        if facet in seen_facets or facet == Facet.PLATFORM:
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
        CONTENT_WEIGHT * _clamp(content)
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
    """Token -> ROM ids, the postings lists candidate generation reads.

    Only ROMs sharing a discriminative token are ever scored against each
    other, which is what keeps a large library tractable.
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
    df_cap = min(
        MAX_CANDIDATE_POSTINGS,
        max(MIN_CANDIDATE_DF, int(total_documents * MAX_CANDIDATE_DF_RATIO)),
    )
    buckets = sorted(
        (
            bucket
            for token in feature.tokens
            if (bucket := postings.get(token)) and len(bucket) <= df_cap
        ),
        key=len,
    )

    candidates: set[int] = set()
    for bucket in buckets:
        # Rarest facet first, so a ROM that trips the ceiling keeps its most
        # discriminative neighbours rather than whichever token came first.
        if len(candidates) >= MAX_CANDIDATES_PER_ROM:
            break
        candidates.update(bucket)

    candidates.discard(feature.rom_id)
    return candidates


def normalise_co_occurrence(
    pair_count: float, left_total: int, right_total: int
) -> float:
    """Cosine-style normalisation of a raw co-occurrence count, damped by support.

    The cosine stops whatever ROM sits in the most collections from looking
    related to everything; the support term stops a pair seen once from
    outscoring one a whole server agrees on. See CO_OCCURRENCE_PRIOR.
    """
    if pair_count <= 0 or left_total <= 0 or right_total <= 0:
        return 0.0

    cosine = pair_count / math.sqrt(left_total * right_total)
    support = pair_count / (pair_count + CO_OCCURRENCE_PRIOR)
    return min(1.0, cosine * support)
