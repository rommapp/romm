from datetime import datetime, timezone

from fastapi import status
from fastapi.testclient import TestClient
from tests.handler.recommendation.test_builder import make_rom

from handler.database import db_rom_handler
from handler.recommendation import SimilarityBuilder, invalidate_cached_feed
from models.platform import Platform
from models.rom import Rom
from models.user import User


def build_library(platform: Platform) -> dict[str, Rom]:
    library = {
        "metroid": make_rom(
            platform,
            "Super Metroid",
            igdb_id=5001,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        ),
        "metroid_2": make_rom(
            platform,
            "Metroid Fusion",
            igdb_id=5002,
            genres=["Platform", "Adventure"],
            franchises=["Metroid"],
            companies=["Nintendo"],
        ),
        "castlevania": make_rom(
            platform,
            "Castlevania SOTN",
            igdb_id=5003,
            genres=["Platform", "Adventure"],
            franchises=["Castlevania"],
            companies=["Konami"],
        ),
    }
    SimilarityBuilder().build()
    return library


def test_similar_roms_returns_library_games(
    client: TestClient, access_token: str, platform: Platform
):
    library = build_library(platform)

    response = client.get(
        f"/api/roms/{library['metroid'].id}/similar",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body
    returned_ids = [entry["rom"]["id"] for entry in body]
    assert library["metroid_2"].id in returned_ids
    # The source game is never among its own recommendations.
    assert library["metroid"].id not in returned_ids


def test_similar_roms_are_ordered_by_score(
    client: TestClient, access_token: str, platform: Platform
):
    library = build_library(platform)

    body = client.get(
        f"/api/roms/{library['metroid'].id}/similar",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    scores = [entry["score"] for entry in body]
    assert scores == sorted(scores, reverse=True)


def test_similar_roms_include_reasons(
    client: TestClient, access_token: str, platform: Platform
):
    library = build_library(platform)

    body = client.get(
        f"/api/roms/{library['metroid'].id}/similar",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    match = next(
        entry for entry in body if entry["rom"]["id"] == library["metroid_2"].id
    )
    assert {"facet": "franchise", "value": "Metroid"} in match["reasons"]


def test_similar_roms_respects_the_limit(
    client: TestClient, access_token: str, platform: Platform
):
    library = build_library(platform)

    body = client.get(
        f"/api/roms/{library['metroid'].id}/similar?limit=1",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    assert len(body) == 1


def test_similar_roms_rejects_an_out_of_range_limit(
    client: TestClient, access_token: str, rom: Rom
):
    response = client.get(
        f"/api/roms/{rom.id}/similar?limit=999",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_similar_roms_404s_for_an_unknown_rom(client: TestClient, access_token: str):
    response = client.get(
        "/api/roms/99999999/similar",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_similar_roms_requires_auth(client: TestClient, rom: Rom):
    assert client.get(f"/api/roms/{rom.id}/similar").status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


def test_similar_roms_is_empty_before_the_index_is_built(
    client: TestClient, access_token: str, rom: Rom
):
    response = client.get(
        f"/api/roms/{rom.id}/similar",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_recommendations_are_seeded_by_play_history(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    library = build_library(platform)

    rom_user = db_rom_handler.get_rom_user(library["metroid"].id, admin_user.id)
    if rom_user is None:
        rom_user = db_rom_handler.add_rom_user(library["metroid"].id, admin_user.id)
    db_rom_handler.update_rom_user(
        rom_user.id,
        {"rating": 10, "last_played": datetime.now(timezone.utc)},
    )
    invalidate_cached_feed(admin_user.id)

    response = client.get(
        "/api/recommendations",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    returned_ids = [entry["rom"]["id"] for entry in body]

    # Loving Super Metroid should surface Metroid Fusion, and never re-suggest
    # the seed itself.
    assert library["metroid_2"].id in returned_ids
    assert library["metroid"].id not in returned_ids


def test_recommendations_attribute_the_seed_game(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    library = build_library(platform)

    rom_user = db_rom_handler.get_rom_user(library["metroid"].id, admin_user.id)
    if rom_user is None:
        rom_user = db_rom_handler.add_rom_user(library["metroid"].id, admin_user.id)
    db_rom_handler.update_rom_user(
        rom_user.id,
        {"rating": 10, "last_played": datetime.now(timezone.utc)},
    )
    invalidate_cached_feed(admin_user.id)

    body = client.get(
        "/api/recommendations",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    match = next(
        entry for entry in body if entry["rom"]["id"] == library["metroid_2"].id
    )
    assert match["seed_rom_id"] == library["metroid"].id
    assert match["seed_rom_name"] == "Super Metroid"


def test_rating_a_game_reshapes_the_feed_without_an_explicit_refresh(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    """Updating rom_user must drop the cached feed, not wait out its TTL."""
    library = build_library(platform)
    headers = {"Authorization": f"Bearer {access_token}"}
    invalidate_cached_feed(admin_user.id)

    # Prime the cache while there is no history at all.
    before = client.get("/api/recommendations", headers=headers).json()
    assert library["metroid_2"].id not in [entry["rom"]["id"] for entry in before]

    response = client.put(
        f"/api/roms/{library['metroid'].id}/props?update_last_played=true",
        headers=headers,
        json={"rating": 10},
    )
    assert response.status_code == status.HTTP_200_OK

    after = client.get("/api/recommendations", headers=headers).json()
    assert library["metroid_2"].id in [entry["rom"]["id"] for entry in after]


def test_recommendations_fall_back_when_there_is_no_history(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    make_rom(
        platform,
        "Acclaimed Game",
        igdb_id=6001,
        genres=["RPG"],
        average_rating=95.0,
    )
    SimilarityBuilder().build()
    invalidate_cached_feed(admin_user.id)

    response = client.get(
        "/api/recommendations",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body
    assert all(
        entry["reasons"] == [{"facet": "top_rated", "value": ""}] for entry in body
    )


def test_recommendations_respect_the_limit(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    build_library(platform)
    invalidate_cached_feed(admin_user.id)

    body = client.get(
        "/api/recommendations?limit=1",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    assert len(body) <= 1


def test_recommendations_reject_an_out_of_range_limit(
    client: TestClient, access_token: str
):
    response = client.get(
        "/api/recommendations?limit=500",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_recommendations_require_auth(client: TestClient):
    assert client.get("/api/recommendations").status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )
