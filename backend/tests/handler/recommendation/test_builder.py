"""End-to-end checks for the similarity index build.

Metadata is seeded by writing `roms.igdb_metadata`, because `roms_metadata` is
a view over generated columns and `roms_facets` is trigger-maintained from the
same source: writing the blob is what drives both.
"""

import pytest

from handler.database import db_recommendation_handler, db_rom_handler
from handler.recommendation import SimilarityBuilder
from models.platform import Platform
from models.rom import Rom


def make_rom(
    platform: Platform,
    name: str,
    *,
    igdb_id: int | None = None,
    genres: list[str] | None = None,
    franchises: list[str] | None = None,
    collections: list[str] | None = None,
    companies: list[str] | None = None,
    similar_igdb_ids: list[int] | None = None,
    average_rating: float | None = None,
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
    if similar_igdb_ids:
        metadata["similar_games"] = [
            {"id": similar_id, "name": f"game-{similar_id}", "type": "similar"}
            for similar_id in similar_igdb_ids
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
            igdb_metadata=metadata,
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
