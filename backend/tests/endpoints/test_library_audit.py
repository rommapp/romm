from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from config.config_manager import config_manager as cm
from handler.database import (
    db_audit_event_handler,
    db_collection_handler,
    db_rom_handler,
)
from handler.database.audit_events_handler import AuditEventFilters
from models.audit_event import AuditEvent
from models.collection import Collection
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _events() -> list[AuditEvent]:
    rows, _ = db_audit_event_handler.get_events(AuditEventFilters(), limit=50, offset=0)
    return [event for event, _ in rows]


def _collection(user: User, *, favorite: bool = False) -> Collection:
    return db_collection_handler.add_collection(
        Collection(
            name="Favorites" if favorite else "Shelf",
            description="",
            is_public=False,
            is_favorite=favorite,
            user_id=user.id,
        )
    )


class TestRomUpdate:
    def test_an_edit_records_what_changed(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        response = client.put(
            f"/api/roms/{rom.id}",
            headers=_auth(access_token),
            data={"name": "Metroid"},
        )

        assert response.status_code == status.HTTP_200_OK
        [event] = _events()
        assert event.action == "rom.edit"
        assert event.target_name == "Metroid"
        assert event.data["changed"] == ["name"]
        assert event.data["name"] == {"from": "test_rom", "to": "Metroid"}

    def test_a_new_provider_id_is_a_manual_match(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        client.put(
            f"/api/roms/{rom.id}",
            headers=_auth(access_token),
            data={"sgdb_id": "4242"},
        )

        [event] = _events()
        assert event.action == "rom.match"
        assert event.data["providers"] == {"sgdb_id": 4242}

    def test_saving_without_changes_records_nothing(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        client.put(
            f"/api/roms/{rom.id}",
            headers=_auth(access_token),
            data={"name": "test_rom"},
        )

        assert _events() == []

    def test_an_unmatch_records_the_ids_it_dropped(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        db_rom_handler.update_rom(rom.id, {"sgdb_id": 4242})

        client.put(
            f"/api/roms/{rom.id}",
            params={"unmatch_metadata": True},
            headers=_auth(access_token),
        )

        [event] = _events()
        assert event.action == "rom.unmatch"
        assert event.data["providers"] == {"sgdb_id": 4242}


def test_a_deleted_rom_keeps_its_name(client: TestClient, access_token: str, rom: Rom):
    response = client.post(
        "/api/roms/delete",
        headers=_auth(access_token),
        json={"roms": [rom.id]},
    )

    assert response.status_code == status.HTTP_200_OK
    [event] = _events()
    assert event.action == "rom.delete"
    assert (event.target_id, event.target_name) == (str(rom.id), "test_rom")
    assert event.data["deleted_from_fs"] is False


def test_a_platform_rename_is_an_edit(
    client: TestClient, access_token: str, platform: Platform
):
    client.put(
        f"/api/platforms/{platform.id}",
        headers=_auth(access_token),
        json={"custom_name": "Famicom"},
    )

    [event] = _events()
    assert event.action == "platform.edit"
    assert event.target_name == "Famicom"
    assert event.data["changed"] == ["custom_name"]


def test_a_config_change_names_its_setting(client: TestClient, access_token: str):
    with patch.object(cm, "add_exclusion"):
        client.post(
            "/api/config/exclude",
            headers=_auth(access_token),
            json={
                "exclusion_type": "EXCLUDED_SINGLE_FILES",
                "exclusion_value": "README.txt",
            },
        )

    [event] = _events()
    assert event.action == "config.update"
    assert event.data == {
        "setting": "exclusion",
        "op": "add",
        "type": "EXCLUDED_SINGLE_FILES",
        "value": "README.txt",
    }


class TestCollections:
    def test_creating_one_is_recorded(self, client: TestClient, access_token: str):
        client.post(
            "/api/collections",
            data={"name": "Shelf"},
            headers=_auth(access_token),
        )

        [event] = _events()
        assert event.action == "collection.create"
        assert event.target_name == "Shelf"

    def test_adding_roms_counts_them(
        self, client: TestClient, access_token: str, admin_user: User, rom: Rom
    ):
        collection = _collection(admin_user)

        client.post(
            f"/api/collections/{collection.id}/roms",
            json={"rom_ids": [rom.id]},
            headers=_auth(access_token),
        )

        [event] = _events()
        assert event.action == "collection.add_roms"
        assert event.data == {"count": 1, "rom_ids": [rom.id]}

    @pytest.mark.parametrize("method", ["post", "delete"])
    def test_a_favourite_toggle_is_not(
        self,
        client: TestClient,
        access_token: str,
        admin_user: User,
        rom: Rom,
        method: str,
    ):
        favorites = _collection(admin_user, favorite=True)

        client.request(
            method.upper(),
            f"/api/collections/{favorites.id}/roms",
            json={"rom_ids": [rom.id]},
            headers=_auth(access_token),
        )

        assert _events() == []
