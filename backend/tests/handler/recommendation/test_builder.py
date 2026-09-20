"""End-to-end checks for the similarity index build.

Metadata is seeded by writing a provider blob on `roms`, because
`roms_metadata` is a view over generated columns and `roms_facets` is
trigger-maintained from the same source: writing the blob is what drives both.
"""

from datetime import datetime, timezone

import pytest

from handler.database import (
    db_platform_handler,
    db_recommendation_handler,
    db_rom_handler,
)
from handler.recommendation import SimilarityBuilder, builder
from handler.recommendation.feed import _cache_key
from models.platform import Platform
from models.rom import Rom
from models.user import User


def make_rom(
    platform: Platform,
    name: str,
    *,
    igdb_id: int | None = None,
    steam_id: int | None = None,
    moby_id: int | None = None,
    genres: list[str] | None = None,
    franchises: list[str] | None = None,
    collections: list[str] | None = None,
    companies: list[str] | None = None,
    similar_igdb_ids: list[int] | None = None,
    port_igdb_ids: list[int] | None = None,
    average_rating: float | None = None,
    rating_votes: int | None = None,
    source: str = "igdb_metadata",
) -> Rom:
    metadata: dict = {
        "genres": genres or [],
        "franchises": franchises or [],
        "collections": collections or [],
        "companies": companies or [],
        "game_modes": [],
    }
    if average_rating is not None:
        # IGDB's total_rating is carried as a string; the generated column casts it.
        metadata["total_rating"] = str(average_rating)
    if rating_votes is not None:
        metadata["total_rating_count"] = rating_votes
    if similar_igdb_ids:
        metadata["similar_games"] = [
            {"id": similar_id, "name": f"game-{similar_id}", "type": "similar"}
            for similar_id in similar_igdb_ids
        ]
    if port_igdb_ids:
        metadata["ports"] = [
            {"id": port_id, "name": f"game-{port_id}", "type": "port"}
            for port_id in port_igdb_ids
        ]

    # Set on insert rather than updated afterwards: the generated columns (and
    # the roms_facets triggers) derive from this blob, so one write is enough.
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=name.lower().replace(" ", "-"),
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
            igdb_id=igdb_id,
            steam_id=steam_id,
            moby_id=moby_id,
            **{source: metadata},
        )
    )


@pytest.fixture
def library(platform: Platform) -> dict[str, Rom]:
    """A small library with one tight cluster and one unrelated outlier.

    Deliberately padded with unrelated games. IDF is relative to the library,
    so on a four-game shelf where three are platformers "Platform" carries
    almost no weight and a genre-only match drops under MIN_EDGE_SCORE -- a
    degenerate case that says nothing about ranking on a real library.
    """
    for index, (genre, franchise, company) in enumerate(
        [
            ("Racing", "Outrun", "Sega"),
            ("Shooter", "Gradius", "Konami"),
            ("Sport", "Tennis", "Namco"),
            ("Fighting", "Street Fighter", "Capcom"),
            ("Simulation", "Sim", "Maxis"),
        ]
    ):
        make_rom(
            platform,
            f"Filler {index}",
            igdb_id=9000 + index,
            genres=[genre],
            franchises=[franchise],
            companies=[company],
        )

    return {
        "metroid": make_rom(
            platform,
            "Super Metroid",
            igdb_id=1001,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        ),
        "metroid_2": make_rom(
            platform,
            "Metroid Fusion",
            igdb_id=1002,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        ),
        "castlevania": make_rom(
            platform,
            "Castlevania SOTN",
            igdb_id=1003,
            genres=["Platform", "Adventure"],
            franchises=["Castlevania"],
            companies=["Konami"],
        ),
        "puzzle": make_rom(
            platform,
            "Tetris",
            igdb_id=1004,
            genres=["Puzzle"],
            companies=["Nintendo"],
        ),
    }


def test_build_creates_edges_for_related_games(library: dict[str, Rom]):
    # Counts are >= rather than ==: the builder indexes the whole library, so
    # ROMs left behind by other tests in this worker's database count too.
    stats = SimilarityBuilder().build()

    assert stats.roms_indexed >= len(library)
    assert stats.edges_written > 0

    edges = db_recommendation_handler.get_similar_rom_edges(library["metroid"].id)
    assert [edge.rom_id for edge in edges]


def test_same_franchise_outranks_same_genre(library: dict[str, Rom]):
    SimilarityBuilder().build()

    edges = db_recommendation_handler.get_similar_rom_edges(library["metroid"].id)
    ranked = [edge.rom_id for edge in edges]

    # Metroid Fusion shares the franchise; Castlevania only shares genres.
    assert ranked[0] == library["metroid_2"].id

    # A genre-only match may fall below MIN_EDGE_SCORE and be dropped entirely,
    # which is a stronger version of the same result. Assert the ordering only
    # when it survived, so the test measures ranking rather than the threshold.
    if library["castlevania"].id in ranked:
        assert ranked.index(library["metroid_2"].id) < ranked.index(
            library["castlevania"].id
        )


def test_unrelated_game_scores_below_a_franchise_match(library: dict[str, Rom]):
    SimilarityBuilder().build()

    by_rom = {
        edge.rom_id: edge.score
        for edge in db_recommendation_handler.get_similar_rom_edges(
            library["metroid"].id
        )
    }

    assert by_rom[library["metroid_2"].id] > by_rom.get(library["puzzle"].id, 0.0)


def test_edges_carry_a_human_readable_reason(library: dict[str, Rom]):
    SimilarityBuilder().build()

    edges = db_recommendation_handler.get_similar_rom_edges(library["metroid"].id)
    match = next(edge for edge in edges if edge.rom_id == library["metroid_2"].id)

    assert {"facet": "franchise", "value": "Metroid"} in match.reasons


def test_a_rom_is_never_similar_to_itself(library: dict[str, Rom]):
    SimilarityBuilder().build()

    for rom in library.values():
        neighbours = db_recommendation_handler.get_similar_rom_edges(rom.id)
        assert rom.id not in {edge.rom_id for edge in neighbours}


def test_region_duplicates_are_not_recommendations(platform: Platform):
    """Two files of the same game must never recommend each other."""
    usa = make_rom(
        platform,
        "Chrono Trigger (USA)",
        igdb_id=2001,
        genres=["RPG"],
        franchises=["Chrono"],
    )
    europe = make_rom(
        platform,
        "Chrono Trigger (Europe)",
        igdb_id=2001,
        genres=["RPG"],
        franchises=["Chrono"],
    )

    SimilarityBuilder().build()

    neighbours = db_recommendation_handler.get_similar_rom_edges(usa.id)
    assert europe.id not in {edge.rom_id for edge in neighbours}


def test_storefront_copies_of_one_game_are_not_recommendations(
    platform: Platform, library: dict[str, Rom]
):
    """Two copies of one Steam game share a steam_id and may have no IGDB match."""
    bundle = make_rom(
        platform,
        "Portal Bundle",
        steam_id=400,
        genres=["Puzzle"],
        franchises=["Portal"],
    )
    single = make_rom(
        platform, "Portal", steam_id=400, genres=["Puzzle"], franchises=["Portal"]
    )
    sequel = make_rom(
        platform, "Portal 2", igdb_id=6002, genres=["Puzzle"], franchises=["Portal"]
    )

    SimilarityBuilder().build()

    neighbours = {
        edge.rom_id
        for edge in db_recommendation_handler.get_similar_rom_edges(bundle.id)
    }
    assert single.id not in neighbours
    assert sequel.id in neighbours


def test_one_users_play_history_does_not_relate_unrelated_games(
    platform: Platform, admin_user: User
):
    """Most servers have one user, whose every played pair is a perfect cosine."""
    tetris = make_rom(platform, "Tetris", igdb_id=3001, genres=["Puzzle"])
    madden = make_rom(platform, "Madden NFL", igdb_id=3002, genres=["Sport"])

    for rom in (tetris, madden):
        rom_user = db_rom_handler.add_rom_user(rom.id, admin_user.id)
        db_rom_handler.update_rom_user(
            rom_user.id, {"last_played": datetime.now(timezone.utc)}
        )

    SimilarityBuilder().build()

    neighbours = {
        edge.rom_id
        for edge in db_recommendation_handler.get_similar_rom_edges(tetris.id)
    }
    assert madden.id not in neighbours


def test_steam_only_games_are_indexed(platform: Platform):
    """Steam feeds the same generated facet columns every other provider does."""
    knight = make_rom(
        platform,
        "Hollow Knight",
        steam_id=367520,
        genres=["Action", "Indie"],
        companies=["Team Cherry"],
        source="steam_metadata",
    )
    silksong = make_rom(
        platform,
        "Hollow Knight Silksong",
        steam_id=1030300,
        genres=["Action", "Indie"],
        companies=["Team Cherry"],
        source="steam_metadata",
    )

    SimilarityBuilder().build()

    neighbours = {
        edge.rom_id
        for edge in db_recommendation_handler.get_similar_rom_edges(knight.id)
    }
    assert silksong.id in neighbours


def test_ports_of_one_game_take_a_single_slot(platform: Platform):
    """Regression: the title check only compared candidates to the source.

    IGDB gives each port its own id, so two ports of one game clear the
    igdb_id check and, sharing no title with the source, both took a slot.
    A section of six then spent two of them naming the same game.
    """
    other_platform = db_platform_handler.add_platform(
        Platform(name="other", slug="other_slug", fs_slug="other_slug")
    )
    source = make_rom(
        platform,
        "100 Classic Games",
        igdb_id=4001,
        genres=["Card & Board Game"],
    )
    port_a = make_rom(platform, "Monopoly", igdb_id=4002, genres=["Card & Board Game"])
    port_b = make_rom(
        other_platform, "Monopoly", igdb_id=4003, genres=["Card & Board Game"]
    )

    SimilarityBuilder().build()

    recommended = {
        edge.rom_id
        for edge in db_recommendation_handler.get_similar_rom_edges(source.id)
    }
    assert len({port_a.id, port_b.id} & recommended) == 1


def test_igdb_similar_games_link_owned_roms(platform: Platform):
    """IGDB's prior should create an edge even without shared metadata."""
    source = make_rom(
        platform,
        "Source Game",
        igdb_id=3001,
        genres=["Shooter"],
        similar_igdb_ids=[3002],
    )
    target = make_rom(platform, "Target Game", igdb_id=3002, genres=["Racing"])
    make_rom(platform, "Unrelated Game", igdb_id=3003, genres=["Racing"])

    SimilarityBuilder().build()

    neighbours = db_recommendation_handler.get_similar_rom_edges(source.id)
    assert target.id in {edge.rom_id for edge in neighbours}


def test_a_port_relation_is_not_a_recommendation(platform: Platform):
    """A port is the same product on other hardware, not a suggestion.

    IGDB's other related buckets feed the prior; `ports` must not, or a game
    scores its own port more highly for being a port of itself. Measured on a
    14,952-game library, that prior was live on 243 pairs whose titles differ
    enough that the duplicate check cannot collapse them, e.g. Robocod: James
    Pond II and James Pond: Codename - Robocod.
    """
    source = make_rom(
        platform,
        "Source Game",
        igdb_id=5001,
        genres=["Shooter"],
        port_igdb_ids=[5002],
    )
    port = make_rom(platform, "Handheld Rework", igdb_id=5002, genres=["Puzzle"])

    SimilarityBuilder().build()

    neighbours = db_recommendation_handler.get_similar_rom_edges(source.id)
    assert port.id not in {edge.rom_id for edge in neighbours}


def test_rebuild_replaces_edges_rather_than_duplicating(library: dict[str, Rom]):
    first = SimilarityBuilder().build()
    second = SimilarityBuilder().build()

    assert first.edges_written == second.edges_written
    assert db_recommendation_handler.count_similarity_edges() == second.edges_written


def test_unidentified_roms_are_not_related_to_each_other(platform: Platform):
    """Sharing only a platform is not similarity.

    Two files that never matched a provider carry nothing but platform (and
    maybe decade), which normalise to identical vectors -- they would score a
    perfect match against each other if they were indexed at all.
    """
    first = make_rom(platform, "Unknown Game A")
    second = make_rom(platform, "Unknown Game B")

    stats = SimilarityBuilder().build()

    assert stats.roms_without_metadata >= 2
    assert db_recommendation_handler.get_similar_rom_edges(first.id) == []
    assert db_recommendation_handler.get_similar_rom_edges(second.id) == []


def test_an_identified_rom_is_not_related_to_an_unidentified_one(platform: Platform):
    identified = make_rom(
        platform, "Known Game", igdb_id=4001, genres=["RPG"], franchises=["Saga"]
    )
    unidentified = make_rom(platform, "Mystery File")

    SimilarityBuilder().build()

    neighbours = db_recommendation_handler.get_similar_rom_edges(identified.id)
    assert unidentified.id not in {edge.rom_id for edge in neighbours}


def test_deleting_a_rom_clears_its_edges_in_both_directions(library: dict[str, Rom]):
    """Edges are cleaned up by the foreign keys, not by an ORM cascade.

    ROMs are removed with a bulk delete, which never triggers an ORM-level
    cascade, so inbound edges would be left dangling without ON DELETE CASCADE
    on both columns.
    """
    SimilarityBuilder().build()
    deleted_id = library["metroid"].id

    assert db_recommendation_handler.get_similar_rom_edges(deleted_id)

    db_rom_handler.delete_rom(deleted_id)

    assert db_recommendation_handler.get_similar_rom_edges(deleted_id) == []
    # The surviving ROM must not still point at the deleted one.
    survivors = db_recommendation_handler.get_similar_rom_edges(library["metroid_2"].id)
    assert deleted_id not in {edge.rom_id for edge in survivors}


def test_build_on_an_empty_library_is_a_no_op():
    stats = SimilarityBuilder().build()

    assert stats.roms_indexed == 0
    assert stats.edges_written == 0


def test_cold_start_prefers_a_well_voted_rating_over_a_lone_perfect_one(
    platform: Platform,
):
    """Regression: the cold-start feed used to be topped by obscure games.

    A single provider scoring something 100 is not evidence it is a great
    game. On a real library exactly fourteen games hit a perfect 100, every
    one a lone ScreenScraper score, and the feed recommended all of them
    ahead of the classics.
    """
    # Shrinkage is toward the library mean, so the library needs a realistic
    # one. With only the two games below, the mean sits between them and the
    # estimator has nothing to pull the outlier down to.
    for index in range(12):
        make_rom(
            platform,
            f"Ordinary Game {index}",
            igdb_id=7100 + index,
            genres=["Action"],
            average_rating=60.0 + index,
            rating_votes=40,
        )

    lone_perfect = make_rom(
        platform,
        "Obscure Sports Title",
        igdb_id=7001,
        genres=["Sport"],
        average_rating=100.0,
        rating_votes=1,
    )
    broadly_loved = make_rom(
        platform,
        "Beloved Classic",
        igdb_id=7002,
        genres=["Adventure"],
        average_rating=94.0,
        rating_votes=1800,
    )

    ranked = db_recommendation_handler.get_fallback_rom_ids(limit=10)

    assert broadly_loved.id in ranked
    assert ranked.index(broadly_loved.id) < ranked.index(lone_perfect.id)


def test_cold_start_still_returns_games_with_no_vote_count(platform: Platform):
    """Most providers report no count at all; those games must not vanish."""
    unvoted = make_rom(
        platform, "Unvoted Game", igdb_id=7003, genres=["RPG"], average_rating=88.0
    )

    assert unvoted.id in db_recommendation_handler.get_fallback_rom_ids(limit=25)


def test_edges_are_written_for_both_directions_of_a_pair(library: dict[str, Rom]):
    """Each pair is scored once, from its lower id, but stores both edges."""
    SimilarityBuilder().build()

    forward = db_recommendation_handler.get_similar_rom_edges(library["metroid"].id)
    backward = db_recommendation_handler.get_similar_rom_edges(library["metroid_2"].id)

    assert library["metroid_2"].id in {edge.rom_id for edge in forward}
    assert library["metroid"].id in {edge.rom_id for edge in backward}


def test_buffer_keeps_only_the_strongest_offers():
    buffer: list[tuple[float, int]] = []
    for rom_id in range(builder.MAX_BUFFERED_NEIGHBOURS + 20):
        builder._offer(buffer, rom_id / 100, rom_id)

    assert len(buffer) == builder.MAX_BUFFERED_NEIGHBOURS
    # The 20 weakest offers were displaced, not the 20 most recent.
    assert min(rom_id for _, rom_id in buffer) == 20


def test_a_duplicate_matched_only_by_mobygames_is_suppressed(
    platform: Platform, library: dict[str, Rom]
):
    """Identity is the list `sibling_roms` matches on, not just IGDB and Steam."""
    original = make_rom(
        platform, "Shinobi", moby_id=5100, genres=["Action"], franchises=["Shinobi"]
    )
    reissue = make_rom(
        platform,
        "Shinobi (Rev 1)",
        moby_id=5100,
        genres=["Action"],
        franchises=["Shinobi"],
    )
    sequel = make_rom(
        platform,
        "Shinobi III",
        igdb_id=5101,
        genres=["Action"],
        franchises=["Shinobi"],
    )

    SimilarityBuilder().build()

    neighbours = {
        edge.rom_id
        for edge in db_recommendation_handler.get_similar_rom_edges(original.id)
    }
    assert reissue.id not in neighbours
    assert sequel.id in neighbours


class TestTopUp:
    """Scoring a handful of ROMs against a library that is already indexed."""

    def test_a_new_rom_gets_edges_without_a_rebuild(
        self, platform: Platform, library: dict[str, Rom]
    ):
        SimilarityBuilder().build()

        newcomer = make_rom(
            platform,
            "Metroid Prime",
            igdb_id=1005,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        )
        assert not db_recommendation_handler.get_similar_rom_edges(newcomer.id)

        stats = SimilarityBuilder().build_for([newcomer.id])

        # Only the newcomer is rescored; the rest of the graph is left alone.
        assert stats.roms_indexed == 1
        neighbours = {
            edge.rom_id
            for edge in db_recommendation_handler.get_similar_rom_edges(newcomer.id)
        }
        assert library["metroid"].id in neighbours

    def test_a_new_rom_reaches_the_games_it_matched(
        self, platform: Platform, library: dict[str, Rom]
    ):
        """Without the reverse edge the newcomer stays out of everyone's feed."""
        SimilarityBuilder().build()

        newcomer = make_rom(
            platform,
            "Metroid Prime",
            igdb_id=1005,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        )
        SimilarityBuilder().build_for([newcomer.id])

        neighbours = {
            edge.rom_id
            for edge in db_recommendation_handler.get_similar_rom_edges(
                library["metroid"].id
            )
        }
        assert newcomer.id in neighbours

    def test_neighbours_keep_the_edges_they_already_had(
        self, platform: Platform, library: dict[str, Rom]
    ):
        SimilarityBuilder().build()

        newcomer = make_rom(
            platform,
            "Metroid Prime",
            igdb_id=1005,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        )
        SimilarityBuilder().build_for([newcomer.id])

        neighbours = {
            edge.rom_id
            for edge in db_recommendation_handler.get_similar_rom_edges(
                library["metroid"].id
            )
        }
        assert library["metroid_2"].id in neighbours

    def test_two_new_roms_do_not_offer_each_other_twice(
        self, platform: Platform, library: dict[str, Rom]
    ):
        """Both directions of a pair of targets are scored once, not once per side."""
        SimilarityBuilder().build()

        first = make_rom(
            platform,
            "Metroid Prime",
            igdb_id=1005,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        )
        second = make_rom(
            platform,
            "Metroid Dread",
            igdb_id=1006,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        )

        SimilarityBuilder().build_for([first.id, second.id])

        for rom in (first, second):
            related = [
                edge.rom_id
                for edge in db_recommendation_handler.get_similar_rom_edges(rom.id)
            ]
            assert len(related) == len(set(related))

    def test_a_rom_with_no_taste_signal_is_counted_not_indexed(
        self, platform: Platform, library: dict[str, Rom]
    ):
        SimilarityBuilder().build()

        bare = make_rom(platform, "Unknown Dump")

        stats = SimilarityBuilder().build_for([bare.id])

        assert stats.roms_indexed == 0
        assert stats.roms_without_metadata == 1

    def test_an_empty_top_up_reads_nothing(self):
        stats = SimilarityBuilder().build_for([])

        assert stats.total == 0
        assert stats.edges_written == 0


class TestTopUpPolicy:
    def test_a_scan_that_touched_the_library_defers_to_a_rebuild(self, monkeypatch):
        enqueued: list[tuple[str, dict]] = []
        monkeypatch.setattr(builder, "MAX_TOP_UP_ROMS", 2)
        monkeypatch.setattr(
            "tasks.registry.enqueue_task",
            lambda name, **kwargs: enqueued.append((name, kwargs)),
        )
        monkeypatch.setattr(
            builder.SimilarityBuilder,
            "build_for",
            lambda self, rom_ids: pytest.fail("should not score inline"),
        )

        builder.top_up_similarity([1, 2, 3])

        assert enqueued == [("build_recommendations", {"task_kwargs": {"force": True}})]

    def test_nothing_scanned_touches_neither_path(self, monkeypatch):
        monkeypatch.setattr(
            builder.SimilarityBuilder,
            "build_for",
            lambda self, rom_ids: pytest.fail("should not score inline"),
        )

        builder.top_up_similarity([])

    def test_a_top_up_that_wrote_edges_drops_the_cached_feeds(
        self, platform: Platform, library: dict[str, Rom], admin_user: User
    ):
        """Every cached ranking was computed against the graph the top-up moved."""
        SimilarityBuilder().build()
        newcomer = make_rom(
            platform,
            "Metroid Prime",
            igdb_id=1005,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        )
        stale_key = _cache_key(admin_user.id, 10)

        builder.top_up_similarity([newcomer.id])

        assert _cache_key(admin_user.id, 10) != stale_key
