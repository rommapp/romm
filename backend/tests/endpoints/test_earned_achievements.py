from typing import Any
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.auth_helpers import hide, user_headers
from tests.factories import make_esrb_rated_rom, make_rom

from handler.database import db_rom_handler, db_user_handler
from models.permission import PermEntity
from models.platform import Platform
from models.user import User

URL = "/api/users/me/earned-achievements"


@pytest.fixture(autouse=True)
def no_media_fill():
    with patch("handler.achievements_handler.schedule_achievement_media_fill"):
        yield


def _catalog(ra_id: int) -> dict[str, Any]:
    return {
        "achievements": [
            {
                "ra_id": ra_id * 10,
                "badge_id": str(ra_id),
                "title": f"Badge {ra_id}",
                "points": 5,
                "type": "progression",
            }
        ]
    }


def _link(user: User, ra_ids: list[int]) -> None:
    db_user_handler.update_user(
        user.id,
        {
            "ra_username": "player",
            "ra_progression": {
                "results": [
                    {
                        "rom_ra_id": ra_id,
                        "earned_achievements": [
                            {
                                "id": str(ra_id),
                                "ra_id": ra_id * 10,
                                "date": "2024-03-02 10:00:00",
                            }
                        ],
                    }
                    for ra_id in ra_ids
                ]
            },
        },
    )


def _game_names(client: TestClient, user: User) -> list[str]:
    response = client.get(URL, headers=user_headers(user))
    assert response.status_code == status.HTTP_200_OK
    return sorted(game["name"] for game in response.json()["games"])


def test_returns_the_progress_of_library_games(
    client: TestClient, viewer_user: User, platform: Platform
):
    played = make_rom(platform, "Played", ra_id=1, ra_metadata=_catalog(1))
    _link(viewer_user, [1])

    response = client.get(URL, headers=user_headers(viewer_user))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["linked"] is True
    assert body["synced"] is True
    assert body["earned"] == 1
    assert body["total"] == 1
    game = body["games"][0]
    assert game["rom_id"] == played.id
    assert game["achievements"][0]["earned"] is True
    assert game["achievements"][0]["earned_at"] == "2024-03-02 10:00:00"


def test_an_unlinked_account_is_empty(client: TestClient, viewer_user: User):
    response = client.get(URL, headers=user_headers(viewer_user))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["linked"] is False
    assert body["games"] == []


def test_a_hidden_rom_is_left_out(
    client: TestClient, viewer_user: User, platform: Platform
):
    shown = make_rom(platform, "Shown", ra_id=1, ra_metadata=_catalog(1))
    hidden = make_rom(platform, "Hidden", ra_id=2, ra_metadata=_catalog(2))
    _link(viewer_user, [1, 2])
    hide(PermEntity.ROMS, hidden.id, user_id=viewer_user.id)

    assert _game_names(client, viewer_user) == [shown.name]


def test_a_hidden_platform_hides_its_games(
    client: TestClient, viewer_user: User, platform: Platform
):
    make_rom(platform, "Shown", ra_id=1, ra_metadata=_catalog(1))
    _link(viewer_user, [1])
    hide(PermEntity.PLATFORMS, platform.id, user_id=viewer_user.id)

    assert _game_names(client, viewer_user) == []


def test_games_above_the_age_limit_are_left_out(
    client: TestClient,
    headers: dict[str, str],
    viewer_user: User,
    platform: Platform,
):
    mature = make_esrb_rated_rom(platform, "Mature", "M")
    everyone = make_esrb_rated_rom(platform, "Everyone", "E")
    for rom, ra_id in ((mature, 1), (everyone, 2)):
        db_rom_handler.update_rom(
            rom.id, {"ra_id": ra_id, "ra_metadata": _catalog(ra_id)}
        )
    group = client.post(
        "/api/permissions/groups",
        headers=headers,
        json={
            "name": "Kids",
            "grants": [
                {"entity": "roms", "action": "read"},
                {"entity": "platforms", "action": "read"},
            ],
            "age_limit": 12,
        },
    )
    assert group.status_code == status.HTTP_201_CREATED, group.text
    joined = client.put(
        f"/api/permissions/users/{viewer_user.id}",
        headers=headers,
        json={"set_group": True, "permission_group_id": group.json()["id"]},
    )
    assert joined.status_code == status.HTTP_200_OK
    _link(viewer_user, [1, 2])

    assert _game_names(client, viewer_user) == ["Everyone"]


@pytest.mark.parametrize(
    "scopes", [["me.read"], ["roms.read"]], ids=["no-roms-read", "no-me-read"]
)
def test_needs_both_read_scopes(
    client: TestClient, viewer_user: User, scopes: list[str]
):
    response = client.get(URL, headers=user_headers(viewer_user, scopes))

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_needs_authentication(client: TestClient):
    response = client.get(URL)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
