from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth import oauth_handler
from handler.database import db_collection_handler, db_rom_handler
from handler.filesystem.resources_handler import FSResourcesHandler
from models.collection import Collection
from models.platform import Platform
from models.rom import Rom
from models.user import User

# Minimal valid PNG (1x1 transparent pixel)
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?\x00\x05\xfe\x02\xfe\xa75\x81\x84"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def collection(admin_user: User) -> Collection:
    return db_collection_handler.add_collection(
        Collection(
            name="Test Collection",
            description="A test collection",
            is_public=False,
            is_favorite=False,
            user_id=admin_user.id,
        )
    )


@pytest.fixture
def favorite_collection(admin_user: User) -> Collection:
    return db_collection_handler.add_collection(
        Collection(
            name="Favorites",
            description="",
            is_public=False,
            is_favorite=True,
            user_id=admin_user.id,
        )
    )


@pytest.fixture
def second_rom(admin_user: User, platform: Platform) -> Rom:
    rom = Rom(
        platform_id=platform.id,
        name="test_rom_2",
        slug="test_rom_slug_2",
        fs_name="test_rom_2.zip",
        fs_name_no_tags="test_rom_2",
        fs_name_no_ext="test_rom_2",
        fs_extension="zip",
        fs_path=f"{platform.slug}/roms",
    )
    return db_rom_handler.add_rom(rom)


@pytest.fixture
def other_user_token(editor_user: User) -> str:
    """Access token for a second user — used to test ownership checks."""
    return oauth_handler.create_access_token(
        data={
            "sub": editor_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(editor_user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )


@pytest.fixture
def other_user_collection(editor_user: User) -> Collection:
    """A collection owned by the editor user, not the admin user."""
    return db_collection_handler.add_collection(
        Collection(
            name="Editor Collection",
            description="",
            is_public=False,
            is_favorite=False,
            user_id=editor_user.id,
        )
    )


# ---------------------------------------------------------------------------
# Collection CRUD
# ---------------------------------------------------------------------------


class TestCreateCollection:
    def test_creates_collection(self, client, access_token: str):
        response = client.post(
            "/api/collections",
            data={"name": "My Games", "description": "Classic games"},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "My Games"
        assert data["description"] == "Classic games"
        assert data["is_favorite"] is False
        assert data["is_public"] is False
        assert data["rom_ids"] == []

    def test_creates_favorite_collection(self, client, access_token: str):
        response = client.post(
            "/api/collections",
            data={"name": "Favorites"},
            params={"is_favorite": True},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_favorite"] is True

    def test_duplicate_name_returns_conflict(
        self, client, access_token: str, collection: Collection
    ):
        response = client.post(
            "/api/collections",
            data={"name": collection.name},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_requires_auth(self, client):
        response = client.post("/api/collections", data={"name": "No Auth"})
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


class TestGetCollections:
    def test_returns_own_collections(
        self, client, access_token: str, collection: Collection
    ):
        response = client.get(
            "/api/collections",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == collection.id
        assert data[0]["name"] == collection.name

    def test_returns_public_collections_from_other_users(
        self,
        client,
        access_token: str,
        admin_user: User,
        editor_user: User,
    ):
        public_col = db_collection_handler.add_collection(
            Collection(
                name="Public Editor Collection",
                description="",
                is_public=True,
                is_favorite=False,
                user_id=editor_user.id,
            )
        )
        db_collection_handler.add_collection(
            Collection(
                name="Private Editor Collection",
                description="",
                is_public=False,
                is_favorite=False,
                user_id=editor_user.id,
            )
        )

        response = client.get(
            "/api/collections",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        ids = [c["id"] for c in response.json()]
        assert public_col.id in ids

    def test_empty_when_no_collections(self, client, access_token: str):
        response = client.get(
            "/api/collections",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestDeleteCollection:
    def test_deletes_own_collection(
        self, client, access_token: str, collection: Collection
    ):
        response = client.delete(
            f"/api/collections/{collection.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert db_collection_handler.get_collection(collection.id) is None

    def test_cannot_delete_other_users_collection(
        self,
        client,
        access_token: str,
        other_user_collection: Collection,
    ):
        response = client.delete(
            f"/api/collections/{other_user_collection.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_404_for_missing_collection(self, client, access_token: str):
        response = client.delete(
            "/api/collections/999999",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# POST /collections/{id}/roms  —  atomic add
# ---------------------------------------------------------------------------


class TestAddRomsToCollection:
    def test_adds_roms_to_empty_collection(
        self, client, access_token: str, collection: Collection, rom: Rom
    ):
        response = client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert rom.id in data["rom_ids"]
        assert data["rom_count"] == 1

    def test_adds_multiple_roms(
        self,
        client,
        access_token: str,
        collection: Collection,
        rom: Rom,
        second_rom: Rom,
    ):
        response = client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id, second_rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert set(data["rom_ids"]) == {rom.id, second_rom.id}
        assert data["rom_count"] == 2

    def test_is_idempotent_no_duplicates(
        self, client, access_token: str, collection: Collection, rom: Rom
    ):
        """Adding a ROM that is already in the collection should not duplicate it."""
        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response = client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["rom_ids"].count(rom.id) == 1
        assert data["rom_count"] == 1

    def test_preserves_existing_roms_when_adding_new(
        self,
        client,
        access_token: str,
        collection: Collection,
        rom: Rom,
        second_rom: Rom,
    ):
        """Adding a new ROM must not remove previously added ROMs."""
        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response = client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [second_rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert set(data["rom_ids"]) == {rom.id, second_rom.id}

    def test_silently_ignores_nonexistent_rom_ids(
        self, client, access_token: str, collection: Collection
    ):
        """Invalid ROM IDs should be filtered out without raising an error."""
        response = client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [999999]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rom_count"] == 0

    def test_returns_404_for_missing_collection(
        self, client, access_token: str, rom: Rom
    ):
        response = client.post(
            "/api/collections/999999/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_403_for_other_users_collection(
        self,
        client,
        access_token: str,
        other_user_collection: Collection,
        rom: Rom,
    ):
        response = client.post(
            f"/api/collections/{other_user_collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_requires_auth(self, client, collection: Collection, rom: Rom):
        response = client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_bumps_updated_at(
        self, client, access_token: str, collection: Collection, rom: Rom
    ):
        # Record time before call (truncated to seconds to match MariaDB precision)
        before_call = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)

        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        refreshed = db_collection_handler.get_collection(collection.id)
        assert refreshed is not None
        assert refreshed.updated_at.replace(tzinfo=None) >= before_call


# ---------------------------------------------------------------------------
# DELETE /collections/{id}/roms  —  atomic remove
# ---------------------------------------------------------------------------


class TestRemoveRomsFromCollection:
    def _seed(self, client, access_token, collection_id, rom_ids):
        """Helper: add ROMs to a collection before testing removal."""
        client.post(
            f"/api/collections/{collection_id}/roms",
            json={"rom_ids": rom_ids},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def test_removes_rom_from_collection(
        self, client, access_token: str, collection: Collection, rom: Rom
    ):
        self._seed(client, access_token, collection.id, [rom.id])

        response = client.request(
            "DELETE",
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert rom.id not in data["rom_ids"]
        assert data["rom_count"] == 0

    def test_removes_only_specified_roms(
        self,
        client,
        access_token: str,
        collection: Collection,
        rom: Rom,
        second_rom: Rom,
    ):
        self._seed(client, access_token, collection.id, [rom.id, second_rom.id])

        response = client.request(
            "DELETE",
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert rom.id not in data["rom_ids"]
        assert second_rom.id in data["rom_ids"]
        assert data["rom_count"] == 1

    def test_removing_absent_rom_is_a_noop(
        self, client, access_token: str, collection: Collection, rom: Rom
    ):
        """Removing a ROM that isn't in the collection should not raise an error."""
        response = client.request(
            "DELETE",
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["rom_count"] == 0

    def test_returns_404_for_missing_collection(
        self, client, access_token: str, rom: Rom
    ):
        response = client.request(
            "DELETE",
            "/api/collections/999999/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_403_for_other_users_collection(
        self,
        client,
        access_token: str,
        other_user_collection: Collection,
        rom: Rom,
    ):
        response = client.request(
            "DELETE",
            f"/api/collections/{other_user_collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_requires_auth(self, client, collection: Collection, rom: Rom):
        response = client.request(
            "DELETE",
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
        )
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_bumps_updated_at(
        self, client, access_token: str, collection: Collection, rom: Rom
    ):
        self._seed(client, access_token, collection.id, [rom.id])
        # Record time before the remove call (truncated to seconds for MariaDB precision)
        before_remove = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)

        client.request(
            "DELETE",
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        refreshed = db_collection_handler.get_collection(collection.id)
        assert refreshed is not None
        assert refreshed.updated_at.replace(tzinfo=None) >= before_remove


# ---------------------------------------------------------------------------
# Race condition regression: concurrent adds must not lose data
# ---------------------------------------------------------------------------


class TestAtomicBehavior:
    def test_sequential_adds_accumulate(
        self,
        client,
        access_token: str,
        collection: Collection,
        rom: Rom,
        second_rom: Rom,
    ):
        """
        Simulates the corrected behavior: two separate add calls, each with a
        single ROM, should result in both ROMs being present — even if they
        arrive close together. This would previously fail under the full-replace
        approach when requests arrived out of order.
        """
        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [second_rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        refreshed = db_collection_handler.get_collection(collection.id)
        assert refreshed is not None
        assert set(refreshed.rom_ids) == {rom.id, second_rom.id}

    def test_interleaved_add_remove_stays_consistent(
        self,
        client,
        access_token: str,
        collection: Collection,
        rom: Rom,
        second_rom: Rom,
    ):
        """
        Add both ROMs, remove one, add it back — final state should reflect
        only the last operation per ROM.
        """
        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id, second_rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        client.request(
            "DELETE",
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        refreshed = db_collection_handler.get_collection(collection.id)
        assert refreshed is not None
        assert set(refreshed.rom_ids) == {rom.id, second_rom.id}


# ---------------------------------------------------------------------------
# Artwork upload validation
# ---------------------------------------------------------------------------


class TestArtworkUpload:
    def test_add_collection_rejects_non_image_artwork(self, client, access_token: str):
        response = client.post(
            "/api/collections",
            data={"name": "Bad Cover Collection"},
            files={"artwork": ("cover.png", b"<script>alert(1)</script>", "image/png")},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "PNG, JPEG, WebP, or GIF" in response.json()["detail"]

    @patch.object(
        FSResourcesHandler,
        "store_artwork",
        new_callable=AsyncMock,
        return_value=("path/to/big.png", "path/to/small.png"),
    )
    def test_add_collection_artwork_uses_detected_extension(
        self,
        store_artwork_mock: AsyncMock,
        client,
        access_token: str,
    ):
        response = client.post(
            "/api/collections",
            data={"name": "Good Cover Collection"},
            files={"artwork": ("payload.html", _PNG_BYTES, "image/png")},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert store_artwork_mock.called
        _, _, file_ext = store_artwork_mock.call_args.args
        assert file_ext == "png"

    def test_update_collection_rejects_non_image_artwork(
        self, client, access_token: str, collection: Collection
    ):
        response = client.put(
            f"/api/collections/{collection.id}",
            data={"rom_ids": "[]"},
            files={"artwork": ("cover.png", b"<script>alert(1)</script>", "image/png")},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "PNG, JPEG, WebP, or GIF" in response.json()["detail"]

    @patch.object(
        FSResourcesHandler,
        "store_artwork",
        new_callable=AsyncMock,
        return_value=("path/to/big.png", "path/to/small.png"),
    )
    def test_update_collection_artwork_uses_detected_extension(
        self,
        store_artwork_mock: AsyncMock,
        client,
        access_token: str,
        collection: Collection,
    ):
        response = client.put(
            f"/api/collections/{collection.id}",
            data={"rom_ids": "[]"},
            files={"artwork": ("payload.html", _PNG_BYTES, "image/png")},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert store_artwork_mock.called
        _, _, file_ext = store_artwork_mock.call_args.args
        assert file_ext == "png"
