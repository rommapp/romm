import pytest

from handler.recommendation.scoring import (
    FACET_WEIGHTS,
    MAX_QUALITY_BONUS,
    Facet,
    RomFeatures,
    blend,
    build_inverted_index,
    build_normalised_vectors,
    build_vector,
    candidate_ids,
    compute_idf,
    content_similarity,
    extract_tokens,
    has_taste_signal,
    make_token,
    normalise,
    normalise_co_occurrence,
    pivot_length,
    quality_bonus,
    release_year_from_epoch,
    shared_reasons,
    token_facet,
    vector_norm,
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

    assert make_token(Facet.GENRE, "Platform") in tokens
    assert make_token(Facet.FRANCHISE, "Metroid") in tokens
    assert make_token(Facet.COLLECTION, "Super Metroid") in tokens
    assert make_token(Facet.COMPANY, "Nintendo") in tokens
    assert make_token(Facet.GAME_MODE, "Single player") in tokens
    assert make_token(Facet.PLATFORM, "7") in tokens
    assert make_token(Facet.DECADE, "1990") in tokens


def test_extract_tokens_namespaces_the_igdb_tag_facets():
    tokens = extract_tokens(
        platform_id=1,
        genres=["Platform"],
        keywords=["metroidvania", "interconnected-world"],
        themes=["Action", "Horror"],
        player_perspectives=["Side view"],
    )

    assert make_token(Facet.KEYWORD, "metroidvania") in tokens
    assert make_token(Facet.THEME, "Horror") in tokens
    assert make_token(Facet.PERSPECTIVE, "Side view") in tokens


def test_igdb_tags_count_as_a_taste_signal():
    """A game with only keywords is still worth indexing."""
    assert has_taste_signal(extract_tokens(platform_id=1, keywords=["roguelike"]))
    assert has_taste_signal(extract_tokens(platform_id=1, themes=["Horror"]))
    assert has_taste_signal(
        extract_tokens(platform_id=1, player_perspectives=["First person"])
    )


def test_curated_facets_explain_a_match_before_keywords():
    """Keywords carry the highest IDF, so they would otherwise own every slot.

    Real data explained a Castlevania match with "frankenstein's monster" and a
    Zelda match with "drawbridge", both of which read as nonsense next to the
    shared franchise or genre that actually drove the score.
    """
    idf = {
        "collection:Castlevania": 2.0,
        "genre:Platform": 1.0,
        # Rare keywords dominate on IDF alone.
        "keyword:frankenstein's monster": 9.0,
    }
    tokens = (
        "collection:Castlevania",
        "genre:Platform",
        "keyword:frankenstein's monster",
    )
    vectors = build_normalised_vectors({1: tokens, 2: tokens}, idf)

    reasons = shared_reasons(vectors[1], vectors[2])

    assert reasons[0]["facet"] == "collection"
    assert reasons[-1]["facet"] == "keyword"


def test_role_split_companies_replace_the_merged_list():
    """Both would double-count a studio for IGDB-matched games only."""
    tokens = extract_tokens(
        platform_id=1,
        genres=["Platform"],
        companies=["Nintendo R&D1", "Playtronic"],
        developers=["Nintendo R&D1"],
        publishers=["Playtronic"],
    )

    assert make_token(Facet.DEVELOPER, "Nintendo R&D1") in tokens
    assert make_token(Facet.PUBLISHER, "Playtronic") in tokens
    assert not any(token_facet(token) == "company" for token in tokens)


def test_the_merged_company_list_is_the_fallback_without_roles():
    """Providers other than IGDB report no roles, so those games keep the old
    behaviour rather than losing the signal entirely."""
    tokens = extract_tokens(
        platform_id=1, genres=["Platform"], companies=["Some Studio"]
    )

    assert make_token(Facet.COMPANY, "Some Studio") in tokens
    assert not any(token_facet(token) == "developer" for token in tokens)


def test_a_shared_developer_outweighs_a_shared_publisher():
    """Regression: matches were being explained by regional distributors.

    Tec Toy and Playtronic distributed hundreds of titles apiece, which put
    creatively unrelated games together under a shared "company".
    """
    idf = {
        "developer:Treasure": 2.0,
        "publisher:Sega": 2.0,
        "genre:Action": 1.0,
    }
    vectors = build_normalised_vectors(
        {
            1: ("genre:Action", "developer:Treasure", "publisher:Sega"),
            2: ("genre:Action", "developer:Treasure"),  # same studio
            3: ("genre:Action", "publisher:Sega"),  # same label only
        },
        idf,
    )

    assert content_similarity(vectors[1], vectors[2]) > content_similarity(
        vectors[1], vectors[3]
    )


def test_company_roles_count_as_a_taste_signal():
    assert has_taste_signal(extract_tokens(platform_id=1, developers=["Treasure"]))
    assert has_taste_signal(extract_tokens(platform_id=1, publishers=["Sega"]))


def test_extract_tokens_skips_blanks_and_deduplicates():
    tokens = extract_tokens(
        platform_id=1,
        genres=["Action", "  ", "", "Action"],
        franchises=None,
    )

    assert tokens.count(make_token(Facet.GENRE, "Action")) == 1
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


def test_build_vector_is_raw_facet_weight_times_idf():
    idf = {"genre:Action": 1.2, "franchise:Metroid": 2.4}
    vector = build_vector(("genre:Action", "franchise:Metroid"), idf)

    assert vector["genre:Action"] == pytest.approx(FACET_WEIGHTS["genre"] * 1.2)
    assert vector["franchise:Metroid"] == pytest.approx(
        FACET_WEIGHTS["franchise"] * 2.4
    )


def test_pivoting_stops_a_sparse_game_outranking_a_rich_one():
    """The defect real data exposed: "Golf" above "Super Mario Sunshine".

    Both candidates share the source's franchise, and the richer one *also*
    shares its genre -- so it is plainly the better match. Under plain L2 the
    richer game is divided by its own longer vector and loses anyway, which is
    exactly how a one-tag entry outranked the real Mario platformers.

    One value per facet throughout, so build_vector's per-facet split is
    neutral here and the test isolates length normalisation.
    """
    idf = {
        token: 1.0
        for token in (
            "genre:a",
            "franchise:b",
            "company:c",
            "theme:d",
            "keyword:x",
            "game_mode:z",
            "perspective:q",
        )
    }
    token_sets = {
        1: ("genre:a", "franchise:b", "company:c", "theme:d"),  # source
        2: ("franchise:b",),  # sparse: shares the franchise only
        3: (  # rich: shares franchise *and* genre, but carries more besides
            "genre:a",
            "franchise:b",
            "keyword:x",
            "game_mode:z",
            "perspective:q",
        ),
    }

    l2 = {}
    for key, tokens in token_sets.items():
        raw = build_vector(tokens, idf)
        l2[key] = normalise(raw, vector_norm(raw))

    # Plain L2 ranks the sparse game first, which is the bug.
    assert content_similarity(l2[1], l2[2]) > content_similarity(l2[1], l2[3])

    pivoted = build_normalised_vectors(token_sets, idf)
    assert content_similarity(pivoted[1], pivoted[3]) > content_similarity(
        pivoted[1], pivoted[2]
    )


def test_pivot_length_blends_towards_the_library_average():
    average = 10.0

    # Partial normalisation pulls both extremes towards the average.
    assert 2.0 < pivot_length(2.0, average, b=0.75) < average
    assert average < pivot_length(20.0, average, b=0.75) < 20.0
    assert pivot_length(average, average, b=0.75) == pytest.approx(average)

    # The shipped default ignores a vector's own length entirely.
    assert pivot_length(2.0, average, b=0.0) == pytest.approx(average)
    assert pivot_length(20.0, average, b=0.0) == pytest.approx(average)


def test_well_documented_games_are_not_penalised_by_default():
    """The shipped default must not let a one-tag game beat a five-tag one.

    Real data: at full L2 normalisation a Mario compilation's nearest matches
    were all 6-8 token entries, with the 12-16 token Mario platformers nowhere
    in the list.
    """
    facets = ("genre", "franchise", "company", "theme", "perspective", "keyword")
    idf = {f"{facet}:v": 1.0 for facet in facets}
    vectors = build_normalised_vectors(
        {
            1: ("genre:v", "franchise:v", "company:v", "theme:v"),
            2: ("genre:v",),
            3: ("genre:v", "franchise:v", "perspective:v", "keyword:v"),
        },
        idf,
    )

    assert content_similarity(vectors[1], vectors[3]) > content_similarity(
        vectors[1], vectors[2]
    )


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


def test_content_similarity_is_symmetric():
    idf = {"genre:Action": 1.0, "franchise:Metroid": 2.0}
    vectors = build_normalised_vectors(
        {1: ("genre:Action", "franchise:Metroid"), 2: ("genre:Action",)}, idf
    )

    assert content_similarity(vectors[1], vectors[2]) == pytest.approx(
        content_similarity(vectors[2], vectors[1])
    )
    assert content_similarity(vectors[1], vectors[2]) > 0


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


def test_context_only_vectors_would_otherwise_match_each_other():
    """Documents the reason context-only ROMs are excluded from the index.

    Two games carrying nothing but platform and decade produce identical
    vectors, so they match each other as strongly as anything possibly can.
    """
    idf = {"platform:7": 2.0, "decade:1990": 1.5}
    tokens = ("platform:7", "decade:1990")

    vectors = build_normalised_vectors({1: tokens, 2: tokens}, idf)
    identical = content_similarity(vectors[1], vectors[2])
    self_match = content_similarity(vectors[1], vectors[1])

    assert identical == pytest.approx(self_match)


def test_co_occurrence_is_damped_by_how_often_it_was_seen():
    # A perfect cosine either way: the only thing separating these is how much
    # evidence sits behind them.
    once = normalise_co_occurrence(1, left_total=1, right_total=1)
    thrice = normalise_co_occurrence(3, left_total=3, right_total=3)
    often = normalise_co_occurrence(10, left_total=10, right_total=10)

    assert once < thrice < often <= 1.0
    # One sighting is what a single-user server produces for every pair of
    # games its owner has played, so it must not read as agreement.
    assert once < 0.3


def test_normalise_co_occurrence_damps_ubiquitous_items():
    # Two games seen together twice, where one appears in everything.
    focused = normalise_co_occurrence(2, left_total=2, right_total=2)
    ubiquitous = normalise_co_occurrence(2, left_total=2, right_total=500)

    assert focused > ubiquitous
    assert focused <= 1.0
    assert normalise_co_occurrence(0, 5, 5) == 0.0
    assert normalise_co_occurrence(3, 0, 5) == 0.0
