from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from rq.job import JobStatus
from tests.factories import (
    STEAM_ID,
    make_platform,
    make_rom,
    make_steam_library_entry,
    steam_player_summary,
)

from handler.database import (
    db_collection_handler,
    db_steam_library_handler,
    db_user_handler,
)
from handler.steam_library_handler import SteamLibraryError
from models.collection import SmartCollection
from models.rom import Rom
from models.user import User
from tasks.registry import SYNC_STEAM_LIBRARIES_TASK

OTHER_STEAM_ID = "76561197960287931"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def half_life() -> Rom:
    return make_rom(make_platform("win"), "Half-Life 2", steam_id=220)


BASE_URL = "https://romm.example"


@pytest.fixture
def resolve_account():
    with patch(
        "endpoints.user.resolve_steam_account", new_callable=AsyncMock
    ) as resolve:
        resolve.return_value = steam_player_summary()
        yield resolve


@pytest.fixture(autouse=True)
def public_base_url():
    with (
        patch("endpoints.user.get_public_base_url", return_value=BASE_URL),
        patch("endpoints.user.STEAM_API_KEY", "key"),
    ):
        yield


@pytest.fixture
def verify_sign_in():
    """Stand in for Steam's check_authentication answer."""
    with patch(
        "endpoints.user.SteamOpenIDService.verify", new_callable=AsyncMock
    ) as verify:
        verify.return_value = STEAM_ID
        yield verify


def _start_login(client: TestClient, user: User, token: str) -> str:
    """Begin a sign-in and hand back the nonce it bound to the session."""
    response = client.get(f"/api/users/{user.id}/steam/login", headers=_bearer(token))
    assert response.status_code == status.HTTP_200_OK
    url = str(response.json()["url"])
    return url.split("state%3D")[-1].split("&")[0]


def _linked_steam_id(user_id: int) -> str | None:
    user = db_user_handler.get_user(user_id)
    assert user is not None
    return user.steam_id


def _sign_in(client: TestClient, user: User, token: str) -> None:
    state = _start_login(client, user, token)
    response = client.get(
        f"/api/users/{user.id}/steam/callback",
        params={"state": state, "openid.claimed_id": "x"},
        headers=_bearer(token),
        follow_redirects=False,
    )
    assert response.status_code == status.HTTP_303_SEE_OTHER


def test_the_login_route_points_at_steam(
    client: TestClient, access_token: str, admin_user: User
):
    response = client.get(
        f"/api/users/{admin_user.id}/steam/login?next=/settings/user/1",
        headers=_bearer(access_token),
    )

    url = response.json()["url"]
    assert url.startswith("https://steamcommunity.com/openid/login?")
    assert "openid.mode=checkid_setup" in url
    assert f"{BASE_URL}/api/users/{admin_user.id}/steam/callback" in url.replace(
        "%3A", ":"
    ).replace("%2F", "/")


def test_the_callback_links_the_account_steam_vouches_for(
    client: TestClient,
    access_token: str,
    admin_user: User,
    verify_sign_in,
    resolve_account,
):
    state = _start_login(client, admin_user, access_token)

    response = client.get(
        f"/api/users/{admin_user.id}/steam/callback",
        params={"state": state, "openid.claimed_id": "x", "openid.mode": "id_res"},
        headers=_bearer(access_token),
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert _linked_steam_id(admin_user.id) == STEAM_ID


def test_a_sign_in_steam_will_not_confirm_links_nothing(
    client: TestClient,
    access_token: str,
    admin_user: User,
    verify_sign_in,
    resolve_account,
):
    verify_sign_in.return_value = None
    state = _start_login(client, admin_user, access_token)

    response = client.get(
        f"/api/users/{admin_user.id}/steam/callback",
        params={"state": state, "openid.claimed_id": "forged"},
        headers=_bearer(access_token),
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert "steam_error" in response.headers["location"]
    assert _linked_steam_id(admin_user.id) is None
    resolve_account.assert_not_awaited()


def test_a_callback_that_did_not_start_here_links_nothing(
    client: TestClient,
    access_token: str,
    admin_user: User,
    verify_sign_in,
    resolve_account,
):
    _start_login(client, admin_user, access_token)

    response = client.get(
        f"/api/users/{admin_user.id}/steam/callback",
        params={"state": "someone-elses-nonce", "openid.claimed_id": "x"},
        headers=_bearer(access_token),
        follow_redirects=False,
    )

    assert response.status_code == status.HTTP_303_SEE_OTHER
    assert _linked_steam_id(admin_user.id) is None
    verify_sign_in.assert_not_awaited()


def test_a_replayed_callback_links_nothing(
    client: TestClient,
    access_token: str,
    admin_user: User,
    verify_sign_in,
    resolve_account,
):
    state = _start_login(client, admin_user, access_token)
    params = {"state": state, "openid.claimed_id": "x"}
    first = client.get(
        f"/api/users/{admin_user.id}/steam/callback",
        params=params,
        headers=_bearer(access_token),
        follow_redirects=False,
    )
    assert first.status_code == status.HTTP_303_SEE_OTHER

    db_user_handler.update_user(admin_user.id, {"steam_id": None})
    replay = client.get(
        f"/api/users/{admin_user.id}/steam/callback",
        params=params,
        headers=_bearer(access_token),
        follow_redirects=False,
    )

    assert "steam_error" in replay.headers["location"]
    assert _linked_steam_id(admin_user.id) is None


def test_an_account_steam_cannot_describe_is_reported(
    client: TestClient,
    access_token: str,
    admin_user: User,
    verify_sign_in,
    resolve_account,
):
    resolve_account.side_effect = SteamLibraryError("No Steam account has the ID")
    state = _start_login(client, admin_user, access_token)

    response = client.get(
        f"/api/users/{admin_user.id}/steam/callback",
        params={"state": state, "openid.claimed_id": "x"},
        headers=_bearer(access_token),
        follow_redirects=False,
    )

    assert "steam_error" in response.headers["location"]
    assert _linked_steam_id(admin_user.id) is None
    user = db_user_handler.get_user(admin_user.id)
    assert user is not None and user.steam_id is None


def test_linking_another_account_forgets_the_old_library(
    client: TestClient,
    access_token: str,
    admin_user: User,
    verify_sign_in,
    resolve_account,
    half_life: Rom,
):
    make_steam_library_entry(admin_user, half_life)
    resolve_account.return_value = steam_player_summary(OTHER_STEAM_ID)
    verify_sign_in.return_value = OTHER_STEAM_ID

    _sign_in(client, admin_user, access_token)

    assert db_steam_library_handler.get_entries(admin_user.id) == []


def test_relinking_the_same_account_keeps_the_library(
    client: TestClient,
    access_token: str,
    admin_user: User,
    verify_sign_in,
    resolve_account,
    half_life: Rom,
):
    make_steam_library_entry(admin_user, half_life)

    _sign_in(client, admin_user, access_token)

    assert len(db_steam_library_handler.get_entries(admin_user.id)) == 1


def test_a_user_cannot_start_a_sign_in_for_someone_else(
    client: TestClient, viewer_access_token: str, admin_user: User
):
    response = client.get(
        f"/api/users/{admin_user.id}/steam/login",
        headers=_bearer(viewer_access_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_unlinking_clears_the_account_and_its_library(
    client: TestClient, access_token: str, admin_user: User, half_life: Rom
):
    db_user_handler.update_user(
        admin_user.id, {"steam_id": STEAM_ID, "steam_persona_name": "Gabe"}
    )
    make_steam_library_entry(admin_user, half_life)

    response = client.delete(
        f"/api/users/{admin_user.id}/steam", headers=_bearer(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["steam_id"] is None
    assert response.json()["steam_persona_name"] is None
    assert db_steam_library_handler.get_entries(admin_user.id) == []


def test_unlinking_empties_an_owned_on_steam_smart_collection(
    client: TestClient, access_token: str, admin_user: User, half_life: Rom
):
    make_steam_library_entry(admin_user, half_life)
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
    client: TestClient, access_token: str, admin_user: User, half_life: Rom
):
    make_steam_library_entry(admin_user, half_life)

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

    with (
        patch("endpoints.tasks.has_live_worker", return_value=True),
        patch("endpoints.user.enqueue_task", return_value=_job()) as enqueue,
    ):
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
def test_sync_needs_a_task_worker(
    client: TestClient, access_token: str, admin_user: User
):
    db_user_handler.update_user(admin_user.id, {"steam_id": STEAM_ID})
    enqueue = MagicMock()

    with (
        patch("endpoints.tasks.has_live_worker", return_value=False),
        patch("endpoints.user.enqueue_task", enqueue),
    ):
        response = client.post(
            f"/api/users/{admin_user.id}/steam/sync", headers=_bearer(access_token)
        )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    enqueue.assert_not_called()


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
