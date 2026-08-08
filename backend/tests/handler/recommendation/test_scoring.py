import math

import pytest

from handler.recommendation.scoring import (
    MAX_QUALITY_BONUS,
    RomFeatures,
    blend,
    build_inverted_index,
    build_vector,
    candidate_ids,
    compute_idf,
    content_similarity,
    extract_tokens,
    has_taste_signal,
    make_token,
    normalise_co_occurrence,
    quality_bonus,
    release_year_from_epoch,
    shared_reasons,
)

# 1991-08-13, the sort of epoch value roms_metadata carries.
SUPER_NES_ERA_EPOCH = 682_041_600


def test_extract_tokens_namespaces_every_facet():
    tokens = extract_tokens(
        platform_id=7,
        genres=["Platform", "Adventure"],
        franchises=["Metroid"],
        collections=["Super Metroid"],
        companies=["Nintendo"],
        game_modes=["Single player"],
        first_release_date=SUPER_NES_ERA_EPOCH,
    )

    assert make_token("genre", "Platform") in tokens
    assert make_token("franchise", "Metroid") in tokens
    assert make_token("collection", "Super Metroid") in tokens
    assert make_token("company", "Nintendo") in tokens
    assert make_token("game_mode", "Single player") in tokens
    assert make_token("platform", "7") in tokens
    assert make_token("decade", "1990") in tokens


def test_extract_tokens_skips_blanks_and_deduplicates():
    tokens = extract_tokens(
        platform_id=1,
        genres=["Action", "  ", "", "Action"],
        franchises=None,
    )

    assert tokens.count(make_token("genre", "Action")) == 1
    assert not any(token.endswith(":") for token in tokens)


def test_release_year_handles_seconds_and_millisecond_epochs():
    assert release_year_from_epoch(SUPER_NES_ERA_EPOCH) == 1991
    # Some provider rows arrive in milliseconds; both must land in the same decade.
    assert release_year_from_epoch(SUPER_NES_ERA_EPOCH * 1000) == 1991
    assert release_year_from_epoch(None) is None
    assert release_year_from_epoch(0) is None


def test_idf_penalises_ubiquitous_tokens():
    documents = [
        ("genre:Action", "franchise:Metroid"),
        ("genre:Action",),
        ("genre:Action",),
        ("genre:Action",),
    ]

    idf = compute_idf(documents, total_documents=4)

    # "Action" is on every game here and says nothing; the franchise is rare.
    assert idf["genre:Action"] < idf["franchise:Metroid"]


def test_a_token_on_every_game_is_worth_almost_nothing():
    """The property the original smoothed IDF failed.

    "Single player" sits on nearly every game in a real library. If it keeps
    meaningful weight it drags unrelated titles up the rankings on nothing but
    a shared game mode.
    """
    documents = [("game_mode:Single player", f"franchise:F{i}") for i in range(50)]

    idf = compute_idf(documents, total_documents=50)

    assert idf["game_mode:Single player"] < 0.05
    # ...while a genuinely rare token stays strong.
    assert idf["franchise:F0"] > 3.0


def test_ubiquitous_facets_cannot_outrank_a_shared_genre():
    """Regression: Tetris used to outrank Super Mario World for Super Metroid.

    Both shared "Nintendo" and "Single player" with the source game, but only
    the platformer shared its genre -- which must dominate.
    """
    library = [
        ("genre:Platform", "company:Nintendo", "game_mode:Single player"),
        ("genre:Platform", "company:Nintendo", "game_mode:Single player"),
        ("genre:Puzzle", "company:Nintendo", "game_mode:Single player"),
        ("genre:RPG", "company:Square", "game_mode:Single player"),
        ("genre:Racing", "company:Sega", "game_mode:Single player"),
        ("genre:RPG", "company:Square", "game_mode:Single player"),
    ]
    idf = compute_idf(library, total_documents=len(library))

    source = build_vector(library[0], idf)
    same_genre = build_vector(library[1], idf)
    same_company_only = build_vector(library[2], idf)

    assert content_similarity(source, same_genre) > content_similarity(
        source, same_company_only
    )


def test_build_vector_is_unit_length():
    idf = {"genre:Action": 1.2, "franchise:Metroid": 2.4}
    vector = build_vector(("genre:Action", "franchise:Metroid"), idf)

    magnitude = math.sqrt(sum(weight**2 for weight in vector.values()))
    assert magnitude == pytest.approx(1.0)


def test_build_vector_drops_zero_weight_tokens():
    vector = build_vector(("genre:Action", "genre:Unknown"), {"genre:Action": 1.0})

    assert "genre:Unknown" not in vector


def test_build_vector_of_unknown_tokens_is_empty():
    assert build_vector(("genre:Action",), {}) == {}


def test_content_similarity_ranks_shared_franchise_above_shared_genre():
    idf = compute_idf(
        [
            ("genre:Action", "franchise:Metroid"),
            ("genre:Action", "franchise:Metroid"),
            ("genre:Action", "franchise:Mario"),
            ("genre:Action", "franchise:Zelda"),
        ],
        total_documents=4,
    )

    source = build_vector(("genre:Action", "franchise:Metroid"), idf)
    same_franchise = build_vector(("genre:Action", "franchise:Metroid"), idf)
    same_genre_only = build_vector(("genre:Action", "franchise:Zelda"), idf)

    assert content_similarity(source, same_franchise) > content_similarity(
        source, same_genre_only
    )


def test_content_similarity_is_symmetric_and_bounded():
    idf = {"genre:Action": 1.0, "franchise:Metroid": 2.0}
    left = build_vector(("genre:Action", "franchise:Metroid"), idf)
    right = build_vector(("genre:Action",), idf)

    assert content_similarity(left, right) == pytest.approx(
        content_similarity(right, left)
    )
    assert 0.0 <= content_similarity(left, right) <= 1.0
    assert content_similarity(left, left) == pytest.approx(1.0)


def test_content_similarity_of_disjoint_vectors_is_zero():
    idf = {"genre:Action": 1.0, "genre:Puzzle": 1.0}
    assert (
        content_similarity(
            build_vector(("genre:Action",), idf), build_vector(("genre:Puzzle",), idf)
        )
        == 0.0
    )


def test_shared_reasons_reports_strongest_facet_first():
    idf = compute_idf(
        [
            ("genre:Action", "franchise:Metroid", "company:Nintendo"),
            ("genre:Action", "franchise:Mario", "company:Nintendo"),
            ("genre:Action", "franchise:Zelda", "company:Sega"),
            ("genre:Action", "franchise:Sonic", "company:Sega"),
        ],
        total_documents=4,
    )
    tokens = ("genre:Action", "franchise:Metroid", "company:Nintendo")
    vector = build_vector(tokens, idf)

    reasons = shared_reasons(vector, vector)

    assert reasons[0] == {"facet": "franchise", "value": "Metroid"}
    # One reason per facet, so the list reads as distinct explanations.
    assert len({reason["facet"] for reason in reasons}) == len(reasons)


def test_shared_reasons_never_explains_a_match_by_platform():
    idf = {"platform:7": 5.0, "genre:Action": 1.0}
    vector = build_vector(("platform:7", "genre:Action"), idf)

    assert all(
        reason["facet"] != "platform" for reason in shared_reasons(vector, vector)
    )


def test_quality_bonus_is_bounded_and_monotonic():
    assert quality_bonus(None) == 0.0
    assert quality_bonus(0) == 0.0
    assert quality_bonus(100) == pytest.approx(MAX_QUALITY_BONUS)
    assert quality_bonus(50) < quality_bonus(90)
    # Providers occasionally emit out-of-range scores.
    assert quality_bonus(140) == pytest.approx(MAX_QUALITY_BONUS)


def test_blend_rewards_every_signal_independently():
    baseline = blend(content=0.5)

    assert blend(content=0.5, igdb_prior=1.0) > baseline
    assert blend(content=0.5, co_play=1.0) > baseline
    assert blend(content=0.5, co_collection=1.0) > baseline
    assert blend(content=0.5, average_rating=95) > baseline


def test_blend_weights_igdb_above_collection_co_membership():
    assert blend(content=0.0, igdb_prior=1.0) > blend(content=0.0, co_collection=1.0)


def test_blend_clamps_out_of_range_signals():
    # A malformed signal must not let a score run away past the maximum.
    assert blend(content=1.0, igdb_prior=50.0, average_rating=100) <= 1.0 + 1e-9


def test_candidate_ids_skips_tokens_that_cover_the_library():
    features = {
        rom_id: RomFeatures(
            rom_id=rom_id,
            platform_id=1,
            tokens=("genre:Action",) + (("franchise:Metroid",) if rom_id < 3 else ()),
        )
        for rom_id in range(1, 301)
    }
    postings = build_inverted_index(features)

    candidates = candidate_ids(features[1], postings, total_documents=len(features))

    # "genre:Action" is on all 300 ROMs, well past the df cap, so only the ROM
    # sharing the rare franchise is considered.
    assert candidates == {2}


def test_candidate_ids_expands_every_token_on_a_small_library():
    # The df ratio must not starve a small shelf of candidates entirely.
    features = {
        rom_id: RomFeatures(rom_id=rom_id, platform_id=1, tokens=("genre:Action",))
        for rom_id in range(1, 5)
    }
    postings = build_inverted_index(features)

    assert candidate_ids(features[1], postings, total_documents=4) == {2, 3, 4}


def test_candidate_ids_excludes_the_source_rom():
    features = {
        1: RomFeatures(rom_id=1, platform_id=1, tokens=("franchise:Metroid",)),
        2: RomFeatures(rom_id=2, platform_id=1, tokens=("franchise:Metroid",)),
    }
    postings = build_inverted_index(features)

    assert 1 not in candidate_ids(features[1], postings, total_documents=2)


def test_has_taste_signal_rejects_context_only_tokens():
    # Platform and decade describe the shelf, not the game.
    assert not has_taste_signal(("platform:7", "decade:1990"))
    assert not has_taste_signal(())
    assert has_taste_signal(("platform:7", "genre:RPG"))
    assert has_taste_signal(("franchise:Metroid",))


def test_context_only_vectors_would_otherwise_match_perfectly():
    """Documents the reason context-only ROMs are excluded from the index."""
    idf = {"platform:7": 2.0, "decade:1990": 1.5}
    tokens = ("platform:7", "decade:1990")

    left = build_vector(tokens, idf)
    right = build_vector(tokens, idf)

    assert content_similarity(left, right) == pytest.approx(1.0)


def test_normalise_co_occurrence_damps_ubiquitous_items():
    # Two games seen together twice, where one appears in everything.
    focused = normalise_co_occurrence(2, left_total=2, right_total=2)
    ubiquitous = normalise_co_occurrence(2, left_total=2, right_total=500)

    assert focused > ubiquitous
    assert focused <= 1.0
    assert normalise_co_occurrence(0, 5, 5) == 0.0
    assert normalise_co_occurrence(3, 0, 5) == 0.0
