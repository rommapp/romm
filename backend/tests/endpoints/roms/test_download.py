from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth import oauth_handler
from handler.database import db_collection_handler, db_rom_handler
from models.collection import Collection, SmartCollection
from models.platform import Platform
from models.rom import Rom, RomFile
from models.user import User


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
    rom = db_rom_handler.add_rom(rom)
    db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="test_rom_2.zip",
            file_path=rom.fs_path,
            file_size_bytes=2000,
        )
    )
    return rom


@pytest.fixture
def collection(admin_user: User, rom: Rom, second_rom: Rom) -> Collection:
    collection = db_collection_handler.add_collection(
        Collection(
            name="Best Games",
            description="",
            is_public=False,
            is_favorite=False,
            user_id=admin_user.id,
        )
    )
    return db_collection_handler.update_collection(
        collection.id, {"name": collection.name}, rom_ids=[rom.id, second_rom.id]
    )


@pytest.fixture
def viewer_token(viewer_user: User) -> str:
    return oauth_handler.create_access_token(
        data={
            "sub": viewer_user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(viewer_user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )


def test_download_roms_by_ids(
    client: TestClient, access_token: str, rom: Rom, rom_file: RomFile, second_rom: Rom
):
    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rom_ids": f"{rom.id},{second_rom.id}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["X-Archive-Files"] == "zip"
    assert "2%20ROMs" in response.headers["Content-Disposition"]
    assert "test_rom.zip" in response.text
    assert "test_rom_2.zip" in response.text


def test_download_roms_by_ids_invalid_format(client: TestClient, access_token: str):
    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rom_ids": "1,abc"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_download_requires_exactly_one_source(
    client: TestClient, access_token: str, rom: Rom, collection: Collection
):
    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rom_ids": str(rom.id), "collection_id": collection.id},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_download_collection(
    client: TestClient,
    access_token: str,
    rom: Rom,
    rom_file: RomFile,
    second_rom: Rom,
    collection: Collection,
):
    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"collection_id": collection.id},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["X-Archive-Files"] == "zip"
    # The zip is named after the collection instead of the generic "N ROMs"
    assert "Best%20Games.zip" in response.headers["Content-Disposition"]
    assert "test_rom.zip" in response.text
    assert "test_rom_2.zip" in response.text


def test_download_collection_explicit_filename_wins(
    client: TestClient,
    access_token: str,
    rom: Rom,
    rom_file: RomFile,
    collection: Collection,
):
    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"collection_id": collection.id, "filename": "custom.zip"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "custom.zip" in response.headers["Content-Disposition"]


def test_download_collection_not_found(client: TestClient, access_token: str):
    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"collection_id": 999999},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_download_private_collection_of_other_user_forbidden(
    client: TestClient, viewer_token: str, collection: Collection
):
    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {viewer_token}"},
        params={"collection_id": collection.id},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_download_public_collection_of_other_user_allowed(
    client: TestClient,
    viewer_token: str,
    rom: Rom,
    rom_file: RomFile,
    collection: Collection,
):
    db_collection_handler.update_collection(collection.id, {"is_public": True})

    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {viewer_token}"},
        params={"collection_id": collection.id},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "test_rom.zip" in response.text


def test_download_smart_collection(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    rom: Rom,
    rom_file: RomFile,
    second_rom: Rom,
):
    smart_collection = db_collection_handler.add_smart_collection(
        SmartCollection(
            name="Platform Games",
            description="",
            is_public=False,
            filter_criteria={"platform_ids": [platform.id]},
            user_id=admin_user.id,
        )
    )

    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"smart_collection_id": smart_collection.id},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "Platform%20Games.zip" in response.headers["Content-Disposition"]
    # Membership is recomputed from the filter criteria at download time
    assert "test_rom.zip" in response.text
    assert "test_rom_2.zip" in response.text


def test_download_private_smart_collection_of_other_user_forbidden(
    client: TestClient,
    viewer_token: str,
    admin_user: User,
    platform: Platform,
):
    smart_collection = db_collection_handler.add_smart_collection(
        SmartCollection(
            name="Admin Only",
            description="",
            is_public=False,
            filter_criteria={"platform_ids": [platform.id]},
            user_id=admin_user.id,
        )
    )

    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {viewer_token}"},
        params={"smart_collection_id": smart_collection.id},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_download_virtual_collection(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    rom: Rom,
    rom_file: RomFile,
    second_rom: Rom,
):
    # The virtual_collections DB view derives a "genre" collection from
    # each rom's igdb_metadata genres, and only materializes it once more
    # than two roms share the value.
    third_rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name="test_rom_3",
            slug="test_rom_slug_3",
            fs_name="test_rom_3.zip",
            fs_name_no_tags="test_rom_3",
            fs_name_no_ext="test_rom_3",
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )
    for rom_id in (rom.id, second_rom.id, third_rom.id):
        db_rom_handler.update_rom(rom_id, {"igdb_metadata": {"genres": ["Action"]}})

    virtual_collections = db_collection_handler.get_virtual_collections("genre")
    assert len(virtual_collections) == 1

    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"virtual_collection_id": virtual_collections[0].id},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "Action.zip" in response.headers["Content-Disposition"]
    assert "test_rom.zip" in response.text
    assert "test_rom_2.zip" in response.text


def test_download_virtual_collection_malformed_id(
    client: TestClient, access_token: str
):
    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"virtual_collection_id": "not-a-valid-id"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_download_empty_collection_returns_404(
    client: TestClient, access_token: str, admin_user: User
):
    empty = db_collection_handler.add_collection(
        Collection(
            name="Empty",
            description="",
            is_public=False,
            is_favorite=False,
            user_id=admin_user.id,
        )
    )

    response = client.get(
        "/api/roms/download",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"collection_id": empty.id},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
