import io
import shutil
import zipfile
from unittest import mock

import pytest
from fastapi import status
from tests._zipfile_shim import reload_zipfile

from handler.database import db_memory_card_handler
from handler.filesystem import fs_asset_handler
from models.assets import MemoryCard, MemoryCardVersion
from models.platform import Platform
from models.user import User
from utils.memory_cards import content_hash_of_bytes, store_memory_card_version


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


@pytest.mark.parametrize(
    "emulator", ["../../etc", "pcsx2/../..", "pcsx2\\..", ".hidden", "/abs"]
)
def test_create_memory_card_unsafe_emulator_rejected(
    client, access_token: str, emulator: str
):
    """The emulator names a folder under the user's card directory, so a value
    that walks out of it is refused at creation rather than at the first write."""
    response = client.post(
        "/api/memory-cards",
        json={"name": "Card", "emulator": emulator},
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
def test_version_listing_flags_an_archive_that_is_gone(
    mock_validate_path,
    client,
    access_token: str,
    memory_card: MemoryCard,
    memory_card_version: MemoryCardVersion,
    tmp_path,
):
    """The history is the only place a user sees a snapshot is unrecoverable
    before clicking download, so the flag is brought back in line here."""
    mock_validate_path.return_value = tmp_path / "not-there.zip"

    response = client.get(
        f"/api/memory-cards/{memory_card.id}/versions", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()[0]["missing_from_fs"] is True
    assert db_memory_card_handler.get_version_by_id(
        memory_card_version.id
    ).missing_from_fs


@mock.patch("endpoints.memory_cards.fs_asset_handler.validate_path")
def test_version_listing_clears_the_flag_when_the_archive_is_back(
    mock_validate_path,
    client,
    access_token: str,
    memory_card: MemoryCard,
    memory_card_version: MemoryCardVersion,
    tmp_path,
):
    db_memory_card_handler.set_version_missing(memory_card_version.id, True)
    restored = tmp_path / "card.zip"
    restored.write_bytes(b"CARD_ZIP")
    mock_validate_path.return_value = restored

    response = client.get(
        f"/api/memory-cards/{memory_card.id}/versions", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()[0]["missing_from_fs"] is False
    assert not db_memory_card_handler.get_version_by_id(
        memory_card_version.id
    ).missing_from_fs


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


# --- Card content ---


@mock.patch("endpoints.memory_cards.fs_asset_handler.validate_path")
def test_owner_downloads_current_card_content(
    mock_validate_path,
    client,
    access_token: str,
    memory_card: MemoryCard,
    memory_card_version: MemoryCardVersion,
    tmp_path,
):
    test_file = tmp_path / "card.zip"
    test_file.write_bytes(b"CURRENT_CARD")
    mock_validate_path.return_value = test_file

    response = client.get(
        f"/api/memory-cards/{memory_card.id}/content", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"CURRENT_CARD"


@mock.patch("endpoints.memory_cards.fs_asset_handler.validate_path")
def test_download_serves_the_newest_version(
    mock_validate_path,
    client,
    access_token: str,
    memory_card: MemoryCard,
    memory_card_version: MemoryCardVersion,
    tmp_path,
):
    newest = db_memory_card_handler.add_version(
        _version_for(memory_card.id, "newer.zip", "ffffffffffffffffffffffffffffffff")
    )
    test_file = tmp_path / "card.zip"
    test_file.write_bytes(b"NEWEST_CARD")
    mock_validate_path.return_value = test_file

    response = client.get(
        f"/api/memory-cards/{memory_card.id}/content", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-disposition"].endswith(f'"{newest.file_name}"')


def test_download_card_without_versions_is_404(
    client, access_token: str, memory_card: MemoryCard
):
    response = client.get(
        f"/api/memory-cards/{memory_card.id}/content", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_other_user_cannot_download_private_card_content(
    client,
    viewer_access_token: str,
    memory_card: MemoryCard,
    memory_card_version: MemoryCardVersion,
):
    response = client.get(
        f"/api/memory-cards/{memory_card.id}/content",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


@mock.patch("endpoints.memory_cards.fs_asset_handler.validate_path")
def test_other_user_downloads_public_card_content(
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
        f"/api/memory-cards/{memory_card.id}/content",
        headers=_auth(viewer_access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.content == b"SHARED_CARD"


# --- Upload ---


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    reload_zipfile()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _version_for(card_id: int, file_name: str, content_hash: str) -> MemoryCardVersion:
    return MemoryCardVersion(
        memory_card_id=card_id,
        file_name=file_name,
        file_name_no_tags=file_name,
        file_name_no_ext=file_name,
        file_extension="zip",
        file_path="psx/memory_cards/pcsx2",
        file_size_bytes=8.0,
        content_hash=content_hash,
    )


def _stub_storage(card_id: int, file_name: str, content_hash: str):
    """Keep a real store_memory_card_version call off the disk: the write is a
    no-op and the scan hands back the version it would have produced."""

    async def _scan(**kwargs):
        return _version_for(card_id, file_name, content_hash)

    return (
        mock.patch(
            "utils.memory_cards.fs_asset_handler.write_file", new=mock.AsyncMock()
        ),
        mock.patch(
            "utils.memory_cards.scan_memory_card_version",
            new=mock.AsyncMock(side_effect=_scan),
        ),
    )


def test_upload_memory_card_version(client, access_token: str, memory_card: MemoryCard):
    content = _zip_bytes({"Mcd001.ps2": b"card data"})
    write_patch, scan_patch = _stub_storage(memory_card.id, "uploaded.zip", "uploaded")
    with write_patch as write_file, scan_patch:
        response = client.post(
            f"/api/memory-cards/{memory_card.id}/versions",
            files={"cardFile": ("card.zip", content, "application/zip")},
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["content_hash"] == "uploaded"
    write_file.assert_awaited_once()
    assert db_memory_card_handler.get_latest_version(memory_card.id).id == (
        response.json()["id"]
    )


def test_upload_of_already_stored_content_still_becomes_newest(
    client, access_token: str, memory_card: MemoryCard
):
    """Re-uploading a card the user downloaded earlier must not be deduplicated
    away: the head version is what the next claim hydrates."""
    content = _zip_bytes({"Mcd001.ps2": b"card data"})
    hash_of_content = content_hash_of_bytes(content)
    assert hash_of_content is not None
    db_memory_card_handler.add_version(
        _version_for(memory_card.id, "older.zip", hash_of_content)
    )

    write_patch, scan_patch = _stub_storage(
        memory_card.id, "reuploaded.zip", hash_of_content
    )
    with write_patch, scan_patch:
        response = client.post(
            f"/api/memory-cards/{memory_card.id}/versions",
            files={"cardFile": ("card.zip", content, "application/zip")},
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_200_OK
    assert len(db_memory_card_handler.get_versions(memory_card.id)) == 2
    assert response.json()["file_name"] == "reuploaded.zip"


def test_upload_non_zip_is_rejected(client, access_token: str, memory_card: MemoryCard):
    """A bare card image is refused here rather than stored: nothing downstream
    would notice until hydrate pushed it and the emulator rejected the card."""
    response = client.post(
        f"/api/memory-cards/{memory_card.id}/versions",
        files={
            "cardFile": ("Mcd001.ps2", b"raw card image", "application/octet-stream")
        },
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.parametrize(
    "entry",
    [
        "../escaped.ps2",
        "sub/../../escaped.ps2",
        "/etc/passwd",
        "..\\..\\escaped.ps2",
        "sub\\..\\..\\escaped.ps2",
        "\\\\server\\share\\escaped.ps2",
    ],
)
def test_upload_with_an_escaping_entry_is_rejected(
    client, access_token: str, memory_card: MemoryCard, entry: str
):
    """RomM keeps the zip whole, so this is the last place that sees the entry
    names before the broker unpacks them onto a container."""
    content = _zip_bytes({entry: b"card data"})
    write_patch, scan_patch = _stub_storage(memory_card.id, "uploaded.zip", "uploaded")
    with write_patch as write_file, scan_patch:
        response = client.post(
            f"/api/memory-cards/{memory_card.id}/versions",
            files={"cardFile": ("card.zip", content, "application/zip")},
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "unsafe path" in response.json()["detail"]
    write_file.assert_not_awaited()
    assert db_memory_card_handler.get_versions(memory_card.id) == []


def test_upload_with_a_symlink_entry_is_rejected(
    client, access_token: str, memory_card: MemoryCard
):
    """A symlink's own name passes every path check; what it points at does
    not, and the extractor this guard protects follows it."""
    reload_zipfile()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        link = zipfile.ZipInfo("Mcd001.ps2")
        # High half of external_attr is the unix mode: symlink, 0777.
        link.external_attr = (0o120777 << 16) | 0o600
        zf.writestr(link, "/etc/passwd")

    write_patch, scan_patch = _stub_storage(memory_card.id, "uploaded.zip", "uploaded")
    with write_patch as write_file, scan_patch:
        response = client.post(
            f"/api/memory-cards/{memory_card.id}/versions",
            files={"cardFile": ("card.zip", buf.getvalue(), "application/zip")},
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "symlink" in response.json()["detail"]
    write_file.assert_not_awaited()
    assert db_memory_card_handler.get_versions(memory_card.id) == []


def test_upload_that_unpacks_past_the_cap_is_rejected(
    client, access_token: str, memory_card: MemoryCard
):
    """A zip's own size says nothing about what it becomes, and the container
    that unpacks it has a disk. The cap is patched down so the test does not
    have to build a gigabyte to prove it is enforced."""
    content = _zip_bytes({"Mcd001.ps2": b"\0" * 4096})
    write_patch, scan_patch = _stub_storage(memory_card.id, "uploaded.zip", "uploaded")
    with (
        mock.patch("utils.memory_cards._CARD_MAX_UNPACKED_BYTES", 1024),
        write_patch as write_file,
        scan_patch,
    ):
        response = client.post(
            f"/api/memory-cards/{memory_card.id}/versions",
            files={"cardFile": ("card.zip", content, "application/zip")},
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "unpacks to over" in response.json()["detail"]
    write_file.assert_not_awaited()
    assert db_memory_card_handler.get_versions(memory_card.id) == []


def test_upload_whose_entries_only_add_up_past_the_cap_is_rejected(
    client, access_token: str, memory_card: MemoryCard
):
    """A card set is several files and the container's disk pays for the whole
    of it, so the budget is spent across entries rather than per entry."""
    content = _zip_bytes({f"Mcd00{slot}.ps2": b"\0" * 512 for slot in range(1, 4)})
    write_patch, scan_patch = _stub_storage(memory_card.id, "uploaded.zip", "uploaded")
    with (
        mock.patch("utils.memory_cards._CARD_MAX_UNPACKED_BYTES", 1024),
        write_patch as write_file,
        scan_patch,
    ):
        response = client.post(
            f"/api/memory-cards/{memory_card.id}/versions",
            files={"cardFile": ("card.zip", content, "application/zip")},
            headers=_auth(access_token),
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "unpacks to over" in response.json()["detail"]
    write_file.assert_not_awaited()
    assert db_memory_card_handler.get_versions(memory_card.id) == []


def test_upload_to_another_users_card_is_404(
    client, viewer_access_token: str, memory_card: MemoryCard
):
    db_memory_card_handler.update_card(memory_card.id, {"is_public": True})
    response = client.post(
        f"/api/memory-cards/{memory_card.id}/versions",
        files={"cardFile": ("card.zip", _zip_bytes({"a": b"b"}), "application/zip")},
        headers=_auth(viewer_access_token),
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


@mock.patch("endpoints.memory_cards.fs_asset_handler.remove_file")
def test_delete_batch_with_a_bad_id_deletes_nothing(
    mock_remove_file,
    client,
    access_token: str,
    memory_card: MemoryCard,
):
    """Deletion is irreversible and runs a transaction per card, so a bad id
    anywhere in the batch must fail before the first card is touched."""
    response = client.post(
        "/api/memory-cards/delete",
        json={"cards": [memory_card.id, 999999]},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_remove_file.assert_not_awaited()
    assert db_memory_card_handler.get_card_by_id(memory_card.id) is not None


@mock.patch(
    "endpoints.memory_cards.fs_asset_handler.remove_file",
    new=mock.AsyncMock(side_effect=PermissionError("read-only mount")),
)
def test_delete_survives_an_archive_that_will_not_budge(
    client,
    access_token: str,
    admin_user: User,
    memory_card: MemoryCard,
    memory_card_version: MemoryCardVersion,
):
    """An orphaned archive is recoverable; a batch that stops half way with
    nothing telling the caller how far it got is not. The unremovable archive
    is on the first card, so the second one proves the batch carried on."""
    second = db_memory_card_handler.add_card(
        MemoryCard(
            user_id=admin_user.id,
            emulator="pcsx2",
            platform_id=memory_card.platform_id,
            name="second_card",
            slot=1,
            is_public=False,
        )
    )
    response = client.post(
        "/api/memory-cards/delete",
        json={"cards": [memory_card.id, second.id]},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert db_memory_card_handler.get_card_by_id(memory_card.id) is None
    assert db_memory_card_handler.get_version_by_id(memory_card_version.id) is None
    assert db_memory_card_handler.get_card_by_id(second.id) is None


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


# --- Version storage ---


async def _hash_on_disk(content: bytes, filename: str) -> str | None:
    """The hash the scan stores, computed the way the scan computes it."""
    path = "memory_card_hash_lockstep"
    await fs_asset_handler.write_file(file=content, path=path, filename=filename)
    try:
        return await fs_asset_handler.compute_content_hash(f"{path}/{filename}")
    finally:
        shutil.rmtree(fs_asset_handler.base_path / path, ignore_errors=True)


@pytest.mark.parametrize(
    ("content", "filename"),
    [
        (_zip_bytes({"Mcd001.ps2": b"card data", "sub/Mcd002.ps2": b"more"}), "c.zip"),
        (b"a card that is not an archive", "c.bin"),
    ],
    ids=["zip", "plain"],
)
async def test_the_in_memory_hash_matches_the_stored_one(content: bytes, filename: str):
    """Dedup compares a hash taken in memory against hashes the scan wrote to
    the database. The two are separate implementations, so a drift between them
    would not fail anywhere: it would quietly stop deduplicating."""
    assert content_hash_of_bytes(content) == await _hash_on_disk(content, filename)


async def test_version_filename_steps_around_an_occupied_name(
    admin_user: User, memory_card: MemoryCard
):
    """Two snapshots in the same millisecond would otherwise share a name, and
    write_file overwrites silently: the first archive's bytes would go while its
    row lived on describing them."""
    taken = {"first": True}

    async def _file_exists(file_path: str) -> bool:
        if taken["first"]:
            taken["first"] = False
            return True
        return False

    with (
        mock.patch(
            "utils.memory_cards.fs_asset_handler.file_exists",
            new=mock.AsyncMock(side_effect=_file_exists),
        ),
        mock.patch(
            "utils.memory_cards.fs_asset_handler.write_file", new=mock.AsyncMock()
        ) as write_file,
        mock.patch(
            "utils.memory_cards.scan_memory_card_version",
            new=mock.AsyncMock(
                side_effect=lambda **kwargs: _version_for(
                    memory_card.id, kwargs["file_name"], "stored"
                )
            ),
        ),
    ):
        assert await store_memory_card_version(
            admin_user, memory_card, b"card data", deduplicate=False
        )

    written = write_file.await_args.kwargs["filename"] if write_file.await_args else ""
    assert "(2)" in written
    assert (
        db_memory_card_handler.get_latest_version(memory_card.id).file_name == written
    )


async def test_a_failed_scan_leaves_no_archive_behind(
    admin_user: User, memory_card: MemoryCard
):
    """No row points at the archive yet, so leaving it there strands bytes
    nothing can reach and no delete would ever clean up."""
    with (
        mock.patch(
            "utils.memory_cards.fs_asset_handler.file_exists",
            new=mock.AsyncMock(return_value=False),
        ),
        mock.patch(
            "utils.memory_cards.fs_asset_handler.write_file", new=mock.AsyncMock()
        ),
        mock.patch(
            "utils.memory_cards.fs_asset_handler.remove_file", new=mock.AsyncMock()
        ) as remove_file,
        mock.patch(
            "utils.memory_cards.scan_memory_card_version",
            new=mock.AsyncMock(side_effect=OSError("scan blew up")),
        ),
    ):
        with pytest.raises(OSError):
            await store_memory_card_version(
                admin_user, memory_card, b"card data", deduplicate=False
            )

    remove_file.assert_awaited_once()
    assert db_memory_card_handler.get_versions(memory_card.id) == []
