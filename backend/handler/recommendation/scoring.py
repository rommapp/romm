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
    # IGDB's curated viewpoint list. "Side view" versus "First person" says
    # more about how a game plays than most genre labels do.
    "perspective": 1.0,
    # A secondary genre axis (Horror, Comedy, Fantasy), curated and low
    # cardinality, so it earns close to a genre's weight.
    "theme": 0.9,
    # Community tags. High cardinality and mixed quality ("motorcycle" sits
    # beside "metroidvania"), so IDF does most of the work and the weight
    # stays below the curated facets. This is the least settled of the
    # weights: on a 12.7k library 0.8 surfaced real golf games for Golf while
    # 0.5 kept 2D Mario platformers ahead of Mario Tennis. Revisit with the
    # inspection tool against a real shelf before trusting it.
    "keyword": 0.7,
    # Who actually made it. Set to what the merged `company` facet carried
    # before the split, so separating the roles redistributes that weight
    # rather than adding new influence.
    #
    # Sweeping it from 1.0 down to 0.4 barely moved results: tight studios
    # (Treasure, Sacnoth) hold their matches at every value because their
    # games also share genre and theme, and wide-ranging ones (Neversoft)
    # only improve at the very bottom of the range.
    "developer": 0.7,
    # Who shipped it. A label spans everything it ever released, and regional
    # distributors land here too -- Tec Toy alone covers 774 games on a 15k
    # library, dense enough that IDF does not suppress it on its own.
    "publisher": 0.25,
    # Used only where no provider reported roles, so the role is unknown and
    # the value could be either. Below genre for the same reason publisher is.
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

# Length-normalisation strength: 1.0 is plain L2, 0.0 scales every vector by
# the library average instead of its own length.
#
# Zero, against the 0.75 that text retrieval uses, because facet counts are not
# verbosity. A long document repeating a word is not more relevant, which is
# why retrieval normalises it away; but a game tagged with three genres and two
# franchises genuinely has more in common than one carrying a single tag, and
# dividing by its own length punished it for being well documented.
#
# Measured on a 12.7k-game library: at 0.75 every top match for a Mario
# compilation was a 6-8 token entry (Golf, F-1 Race, Pinball); at 0.0 they were
# 12-16 token entries (Yoshi's Island, Super Mario 64, Super Mario Kart). The
# feared popularity bias did not appear -- across 300 sampled games the most
# repeated recommendation fell from 6 lists to 3, and distinct results rose
# from 1363 to 1384.
PIVOT_B: Final = 0.0

# Release proximity matters, but only softly: a decade token already carries
# most of the era signal.
SAME_DECADE_TOKEN: Final = "decade"


# Facets that describe the game itself rather than where it sits on the shelf.
# A ROM carrying none of these has nothing to be similar *about*: platform and
# decade alone would make every unmatched file in a folder a perfect match for
# every other, since both vectors normalise to the same thing.
TASTE_FACETS: Final[frozenset[str]] = frozenset(
    {
        "genre",
        "franchise",
        "collection",
        "company",
        "game_mode",
        "developer",
        "publisher",
        "keyword",
        "theme",
        "perspective",
    }
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
    # Normalised title, used to spot the same game released on another
    # platform, which IGDB indexes as a separate id.
    title_key: str | None = None


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
    company_facets: tuple[tuple[str, Sequence[str] | None], ...] = (
        (("developer", developers), ("publisher", publishers))
        if has_roles
        else (("company", companies),)
    )

    for facet, values in (
        ("genre", genres),
        ("franchise", franchises),
        ("collection", collections),
        *company_facets,
        ("game_mode", game_modes),
        ("keyword", keywords),
        ("theme", themes),
        ("perspective", player_perspectives),
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
    """Raw facet-weighted IDF vector, before any length normalisation.

    A facet's weight is split across however many values it holds, so one
    franchise counts for more than one of six. Without it, a compilation
    carrying several franchises matches strongly on all of them: the SNES
    Mario compilation pulled in Mario Tennis and Mario Party ahead of the 2D
    platformers it actually resembles.

    Splitting by sqrt rather than the count itself keeps a multi-value facet
    worth more in total than a single-value one -- three genres really is more
    information than one -- while stopping it from scaling linearly.
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
    """Blend a vector's own length with the library average.

    Plain L2 normalisation (b=1) divides by the vector's own length, which
    hands sparsely-tagged games an advantage: with only a few tokens each one
    carries enormous weight, so a game sharing one broad facet outscores a
    richly-tagged game sharing three. See PIVOT_B for why the default is 0.
    """
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

    Needs the full set up front because the pivot is relative to the library,
    the same way the IDF weighting is.
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
    # Keywords are ranked last regardless of contribution. They are the rarest
    # tokens, so they carry the highest IDF and would otherwise always win the
    # slot -- explaining a match with "drawbridge" or "frankenstein's monster"
    # when the two games are really both Castlevanias. They still earn a slot
    # once the curated facets are exhausted, where "interconnected-world" says
    # something no genre can.
    contributions.sort(
        key=lambda pair: (token_facet(pair[1]) == "keyword", -pair[0], pair[1])
    )

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
