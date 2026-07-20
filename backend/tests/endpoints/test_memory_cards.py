from unittest import mock

from fastapi import status

from handler.database import db_memory_card_handler
from models.assets import MemoryCard, MemoryCardVersion
from models.platform import Platform


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Create ---


def test_create_memory_card(client, access_token: str, platform: Platform):
    response = client.post(
        "/api/memory-cards",
        json={"name": "My Card", "emulator": "pcsx2", "platform_id": platform.id},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["name"] == "My Card"
    assert body["emulator"] == "pcsx2"
    assert body["platform_id"] == platform.id
    assert body["slot"] == 1
    assert body["is_public"] is False


def test_create_memory_card_without_platform(client, access_token: str):
    response = client.post(
        "/api/memory-cards",
        json={"name": "No Platform", "emulator": "pcsx2"},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["platform_id"] is None


def test_create_memory_card_blank_name_rejected(client, access_token: str):
    response = client.post(
        "/api/memory-cards",
        json={"name": "   ", "emulator": "pcsx2"},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_memory_card_unknown_platform_rejected(client, access_token: str):
    response = client.post(
        "/api/memory-cards",
        json={"name": "Card", "emulator": "pcsx2", "platform_id": 99999},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- List (own) ---


def test_list_own_memory_cards(client, access_token: str, memory_card: MemoryCard):
    response = client.get("/api/memory-cards", headers=_auth(access_token))
    assert response.status_code == status.HTTP_200_OK
    ids = [c["id"] for c in response.json()]
    assert memory_card.id in ids


def test_list_memory_cards_filtered_by_emulator(
    client, access_token: str, memory_card: MemoryCard
):
    matching = client.get(
        "/api/memory-cards?emulator=pcsx2", headers=_auth(access_token)
    )
    assert matching.status_code == status.HTTP_200_OK
    assert [c["id"] for c in matching.json()] == [memory_card.id]

    other = client.get(
        "/api/memory-cards?emulator=dolphin", headers=_auth(access_token)
    )
    assert other.status_code == status.HTTP_200_OK
    assert other.json() == []


def test_list_does_not_show_another_users_private_card(
    client, viewer_access_token: str, memory_card: MemoryCard
):
    response = client.get("/api/memory-cards", headers=_auth(viewer_access_token))
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


# --- Shared ---


def test_shared_lists_own_and_public_cards(
    client, viewer_access_token: str, memory_card: MemoryCard
):
    # Private card of another user is not visible.
    hidden = client.get(
        "/api/memory-cards/shared?emulator=pcsx2", headers=_auth(viewer_access_token)
    )
    assert hidden.status_code == status.HTTP_200_OK
    assert hidden.json() == []

    # Once public, it shows up enriched with the owner's username.
    db_memory_card_handler.update_card(memory_card.id, {"is_public": True})
    shared = client.get(
        "/api/memory-cards/shared?emulator=pcsx2", headers=_auth(viewer_access_token)
    )
    assert shared.status_code == status.HTTP_200_OK
    body = shared.json()
    assert len(body) == 1
    assert body[0]["id"] == memory_card.id
    assert body[0]["username"] == "test_admin"


# --- Get one ---


def test_get_own_memory_card(client, access_token: str, memory_card: MemoryCard):
    response = client.get(
        f"/api/memory-cards/{memory_card.id}", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == memory_card.id


def test_get_other_users_private_card_is_404(
    client, viewer_access_token: str, memory_card: MemoryCard
):
    response = client.get(
        f"/api/memory-cards/{memory_card.id}", headers=_auth(viewer_access_token)
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_other_users_public_card(
    client, viewer_access_token: str, memory_card: MemoryCard
):
    db_memory_card_handler.update_card(memory_card.id, {"is_public": True})
    response = client.get(
        f"/api/memory-cards/{memory_card.id}", headers=_auth(viewer_access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == memory_card.id


def test_get_missing_memory_card_is_404(client, access_token: str):
    response = client.get("/api/memory-cards/99999", headers=_auth(access_token))
    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- Versions ---


def test_list_memory_card_versions(
    client,
    access_token: str,
    memory_card: MemoryCard,
    memory_card_version: MemoryCardVersion,
):
    response = client.get(
        f"/api/memory-cards/{memory_card.id}/versions", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == memory_card_version.id
    assert body[0]["content_hash"] == "0123456789abcdef0123456789abcdef"
    assert body[0]["download_path"].startswith(
        f"/api/memory-cards/versions/{memory_card_version.id}/content?timestamp="
    )


@mock.patch("endpoints.memory_cards.fs_asset_handler.validate_path")
def test_owner_downloads_version_content(
    mock_validate_path,
    client,
    access_token: str,
    memory_card_version: MemoryCardVersion,
    tmp_path,
):
    test_file = tmp_path / "card.zip"
    test_file.write_bytes(b"CARD_ZIP")
    mock_validate_path.return_value = test_file

    response = client.get(
        f"/api/memory-cards/versions/{memory_card_version.id}/content",
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"CARD_ZIP"


def test_other_user_cannot_download_private_version(
    client, viewer_access_token: str, memory_card_version: MemoryCardVersion
):
    response = client.get(
        f"/api/memory-cards/versions/{memory_card_version.id}/content",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@mock.patch("endpoints.memory_cards.fs_asset_handler.validate_path")
def test_other_user_downloads_public_version(
    mock_validate_path,
    client,
    viewer_access_token: str,
    memory_card: MemoryCard,
    memory_card_version: MemoryCardVersion,
    tmp_path,
):
    db_memory_card_handler.update_card(memory_card.id, {"is_public": True})
    test_file = tmp_path / "card.zip"
    test_file.write_bytes(b"SHARED_CARD")
    mock_validate_path.return_value = test_file

    response = client.get(
        f"/api/memory-cards/versions/{memory_card_version.id}/content",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"SHARED_CARD"


def test_download_missing_version_is_404(client, access_token: str):
    response = client.get(
        "/api/memory-cards/versions/99999/content", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- Rename ---


def test_rename_memory_card(client, access_token: str, memory_card: MemoryCard):
    response = client.put(
        f"/api/memory-cards/{memory_card.id}",
        json={"name": "Renamed"},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["name"] == "Renamed"


def test_rename_blank_name_rejected(client, access_token: str, memory_card: MemoryCard):
    response = client.put(
        f"/api/memory-cards/{memory_card.id}",
        json={"name": "   "},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_other_user_cannot_rename_card(
    client, viewer_access_token: str, memory_card: MemoryCard
):
    response = client.put(
        f"/api/memory-cards/{memory_card.id}",
        json={"name": "Hijacked"},
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- Visibility ---


def test_toggle_visibility(client, access_token: str, memory_card: MemoryCard):
    response = client.put(
        f"/api/memory-cards/{memory_card.id}/visibility",
        json={"is_public": True},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["is_public"] is True

    refreshed = db_memory_card_handler.get_card_by_id(memory_card.id)
    assert refreshed is not None and refreshed.is_public is True


def test_other_user_cannot_change_visibility(
    client, viewer_access_token: str, memory_card: MemoryCard
):
    response = client.put(
        f"/api/memory-cards/{memory_card.id}/visibility",
        json={"is_public": True},
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- Delete ---


@mock.patch("endpoints.memory_cards.fs_asset_handler.remove_file")
def test_delete_own_card(
    mock_remove_file,
    client,
    access_token: str,
    memory_card: MemoryCard,
    memory_card_version: MemoryCardVersion,
):
    response = client.post(
        "/api/memory-cards/delete",
        json={"cards": [memory_card.id]},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [memory_card.id]

    # The version's archive is removed, and both rows are gone.
    mock_remove_file.assert_awaited_once()
    assert db_memory_card_handler.get_card_by_id(memory_card.id) is None
    assert db_memory_card_handler.get_version_by_id(memory_card_version.id) is None


def test_delete_empty_list_rejected(client, access_token: str):
    response = client.post(
        "/api/memory-cards/delete",
        json={"cards": []},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_other_user_cannot_delete_card(
    client, viewer_access_token: str, memory_card: MemoryCard
):
    response = client.post(
        "/api/memory-cards/delete",
        json={"cards": [memory_card.id]},
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # The card survives the rejected delete.
    assert db_memory_card_handler.get_card_by_id(memory_card.id) is not None
