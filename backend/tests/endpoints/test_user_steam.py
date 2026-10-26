from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from rq.job import JobStatus
from tests.factories import make_platform, make_rom

from handler.database import (
    db_collection_handler,
    db_steam_library_handler,
    db_user_handler,
)
from handler.steam_library_handler import SteamLibraryError
from models.collection import SmartCollection
from models.steam_library import SteamLibraryEntry
from models.user import User
from tasks.registry import SYNC_STEAM_LIBRARIES_TASK

STEAM_ID = "76561197960287930"
OTHER_STEAM_ID = "76561197960287931"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _summary(steam_id: str = STEAM_ID, name: str = "Gabe") -> dict[str, object]:
    return {
        "steamid": steam_id,
        "personaname": name,
        "profileurl": f"https://steamcommunity.com/profiles/{steam_id}/",
        "communityvisibilitystate": 3,
    }


def _own_one_game(user: User) -> None:
    rom = make_rom(make_platform("win"), "Half-Life 2", steam_id=220)
    db_steam_library_handler.replace_entries(
        user.id,
        [SteamLibraryEntry(rom_id=rom.id, steam_app_id=220, playtime_minutes=5)],
    )


@pytest.fixture
def resolve_profile():
    with patch(
        "endpoints.user.resolve_steam_profile", new_callable=AsyncMock
    ) as resolve:
        resolve.return_value = _summary()
        yield resolve


def test_links_the_resolved_account(
    client: TestClient, access_token: str, admin_user: User, resolve_profile
):
    response = client.put(
        f"/api/users/{admin_user.id}/steam",
        json={"profile": "https://steamcommunity.com/id/gabe"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["steam_id"] == STEAM_ID
    assert response.json()["steam_persona_name"] == "Gabe"
    resolve_profile.assert_awaited_once_with("https://steamcommunity.com/id/gabe")


def test_a_profile_steam_cannot_resolve_is_a_bad_request(
    client: TestClient, access_token: str, admin_user: User, resolve_profile
):
    resolve_profile.side_effect = SteamLibraryError("No Steam profile uses it")

    response = client.put(
        f"/api/users/{admin_user.id}/steam",
        json={"profile": "nobody"},
        headers=_bearer(access_token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "No Steam profile uses it"
    user = db_user_handler.get_user(admin_user.id)
    assert user is not None and user.steam_id is None


def test_linking_another_account_forgets_the_old_library(
    client: TestClient, access_token: str, admin_user: User, resolve_profile
):
    db_user_handler.update_user(admin_user.id, {"steam_id": STEAM_ID})
    _own_one_game(admin_user)
    resolve_profile.return_value = _summary(OTHER_STEAM_ID)

    client.put(
        f"/api/users/{admin_user.id}/steam",
        json={"profile": OTHER_STEAM_ID},
        headers=_bearer(access_token),
    )

    assert db_steam_library_handler.get_entries(admin_user.id) == []


def test_relinking_the_same_account_keeps_the_library(
    client: TestClient, access_token: str, admin_user: User, resolve_profile
):
    db_user_handler.update_user(admin_user.id, {"steam_id": STEAM_ID})
    _own_one_game(admin_user)

    client.put(
        f"/api/users/{admin_user.id}/steam",
        json={"profile": STEAM_ID},
        headers=_bearer(access_token),
    )

    assert len(db_steam_library_handler.get_entries(admin_user.id)) == 1


def test_a_user_cannot_link_someone_elses_account(
    client: TestClient, viewer_access_token: str, admin_user: User, resolve_profile
):
    response = client.put(
        f"/api/users/{admin_user.id}/steam",
        json={"profile": STEAM_ID},
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    resolve_profile.assert_not_awaited()


def test_unlinking_clears_the_account_and_its_library(
    client: TestClient, access_token: str, admin_user: User
):
    db_user_handler.update_user(
        admin_user.id, {"steam_id": STEAM_ID, "steam_persona_name": "Gabe"}
    )
    _own_one_game(admin_user)

    response = client.delete(
        f"/api/users/{admin_user.id}/steam", headers=_bearer(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["steam_id"] is None
    assert response.json()["steam_persona_name"] is None
    assert db_steam_library_handler.get_entries(admin_user.id) == []


def test_unlinking_empties_an_owned_on_steam_smart_collection(
    client: TestClient, access_token: str, admin_user: User
):
    db_user_handler.update_user(admin_user.id, {"steam_id": STEAM_ID})
    _own_one_game(admin_user)
    smart_collection = db_collection_handler.add_smart_collection(
        SmartCollection(
            name="Owned on Steam",
            description="",
            user_id=admin_user.id,
            filter_criteria={"owned_on_steam": True},
        )
    )
    db_collection_handler.refresh_smart_collections()
    seeded = db_collection_handler.get_smart_collection(smart_collection.id)
    assert seeded is not None and seeded.rom_count == 1

    client.delete(f"/api/users/{admin_user.id}/steam", headers=_bearer(access_token))

    after = db_collection_handler.get_smart_collection(smart_collection.id)
    assert after is not None and after.rom_count == 0


def test_lists_the_owned_app_ids(
    client: TestClient, access_token: str, admin_user: User
):
    _own_one_game(admin_user)

    response = client.get(
        f"/api/users/{admin_user.id}/steam/library", headers=_bearer(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [220]


def test_a_user_cannot_list_someone_elses_library(
    client: TestClient, viewer_access_token: str, admin_user: User
):
    response = client.get(
        f"/api/users/{admin_user.id}/steam/library",
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def _job() -> SimpleNamespace:
    return SimpleNamespace(
        id="job-1",
        meta={"task_name": "Steam library sync"},
        created_at=None,
        enqueued_at=None,
        get_status=lambda refresh: JobStatus.QUEUED,
    )


@patch("endpoints.user.STEAM_API_KEY", "key")
def test_sync_queues_the_task_for_that_user(
    client: TestClient, access_token: str, admin_user: User
):
    db_user_handler.update_user(admin_user.id, {"steam_id": STEAM_ID})

    with patch("endpoints.user.enqueue_task", return_value=_job()) as enqueue:
        response = client.post(
            f"/api/users/{admin_user.id}/steam/sync", headers=_bearer(access_token)
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["task_id"] == "job-1"
    enqueue.assert_called_once_with(
        SYNC_STEAM_LIBRARIES_TASK,
        task_kwargs={"user_id": admin_user.id},
        run_by_user_id=admin_user.id,
    )


@patch("endpoints.user.STEAM_API_KEY", "key")
def test_sync_needs_a_linked_account(
    client: TestClient, access_token: str, admin_user: User
):
    enqueue = MagicMock()
    with patch("endpoints.user.enqueue_task", enqueue):
        response = client.post(
            f"/api/users/{admin_user.id}/steam/sync", headers=_bearer(access_token)
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    enqueue.assert_not_called()


@patch("endpoints.user.STEAM_API_KEY", None)
def test_sync_needs_an_api_key(client: TestClient, access_token: str, admin_user: User):
    db_user_handler.update_user(admin_user.id, {"steam_id": STEAM_ID})

    response = client.post(
        f"/api/users/{admin_user.id}/steam/sync", headers=_bearer(access_token)
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "STEAM_API_KEY" in response.json()["detail"]
