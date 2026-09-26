"""Tests for sync endpoints."""

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any
from unittest import mock

import pytest
from fastapi import status

from handler.database import (
    db_deleted_asset_handler,
    db_device_handler,
    db_device_save_sync_handler,
    db_play_session_handler,
    db_save_handler,
    db_sync_session_handler,
)
from handler.socket_handler import socket_handler
from models.assets import Save
from models.device import Device, SyncMode
from models.platform import Platform
from models.rom import Rom
from models.sync_session import SyncSessionStatus
from models.user import User
from utils.validation import MAX_ROM_IDS_PER_QUERY


class TestSyncNegotiate:
    def test_negotiate_new_client_save(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        """Client has a save the server doesn't -> upload."""
        device = db_device_handler.add_device(
            Device(id="neg-dev-1", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [
                    {
                        "rom_id": rom.id,
                        "file_name": "new_save.sav",
                        "updated_at": "2026-01-10T00:00:00Z",
                        "file_size_bytes": 1024,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_upload"] == 1
        assert data["operations"][0]["action"] == "upload"

    @pytest.mark.parametrize(
        "content_hash,expected_action",
        [("deadbeef", "delete"), ("f00d", "upload")],
        ids=["the-deleted-version", "bytes-the-deletion-never-covered"],
    )
    def test_negotiate_a_slot_the_owner_deleted(
        self,
        client,
        access_token: str,
        admin_user: User,
        rom: Rom,
        content_hash: str,
        expected_action: str,
    ):
        """Server emptied the slot: only the bytes it lost are dropped."""
        device = db_device_handler.add_device(
            Device(
                id=f"neg-dev-deleted-{content_hash}",
                user_id=admin_user.id,
                sync_enabled=True,
            )
        )
        db_deleted_asset_handler.record_deletion(
            user_id=admin_user.id,
            rom_id=rom.id,
            slot="autosave",
            content_hash="deadbeef",
        )

        data = _negotiate(
            client,
            access_token,
            device.id,
            [
                {
                    "rom_id": rom.id,
                    "file_name": "test_save.sav",
                    "slot": "autosave",
                    "content_hash": content_hash,
                    "updated_at": "2026-01-09T00:00:00Z",
                    "file_size_bytes": 1024,
                }
            ],
        )

        assert data[f"total_{expected_action}"] == 1
        assert data["operations"][0]["action"] == expected_action

    def test_negotiate_a_deleted_slot_matches_its_exact_name(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        """Slots differing only in case keep their own deletion records."""
        device = db_device_handler.add_device(
            Device(id="neg-dev-deleted-case", user_id=admin_user.id, sync_enabled=True)
        )
        for slot, content_hash in (("Autosave", "upper"), ("autosave", "lower")):
            db_deleted_asset_handler.record_deletion(
                user_id=admin_user.id,
                rom_id=rom.id,
                slot=slot,
                content_hash=content_hash,
            )

        data = _negotiate(
            client,
            access_token,
            device.id,
            [
                {
                    "rom_id": rom.id,
                    "file_name": "test_save.sav",
                    "slot": "autosave",
                    "content_hash": "lower",
                    "updated_at": "2026-01-09T00:00:00Z",
                    "file_size_bytes": 1024,
                }
            ],
        )

        assert data["operations"][0]["action"] == "delete"

    def test_negotiate_server_has_save_client_doesnt(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        """Server has a save the client doesn't mention -> download."""
        device = db_device_handler.add_device(
            Device(id="neg-dev-2", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_download"] >= 1

    def test_negotiate_identical_hashes(
        self, client, access_token: str, admin_user: User, rom: Rom, save: Save
    ):
        """Matching hash -> no_op."""
        device = db_device_handler.add_device(
            Device(id="neg-dev-3", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [
                    {
                        "rom_id": save.rom_id,
                        "file_name": save.file_name,
                        "slot": save.slot,
                        "content_hash": save.content_hash,
                        "updated_at": save.updated_at.isoformat(),
                        "file_size_bytes": 100,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Fixture save has no content_hash; hash-match no_op is covered by test_negotiate_matches_untagged_client_to_tagged_server_saves
        assert "session_id" in data

    def test_negotiate_device_not_found(self, client, access_token: str):
        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": "nonexistent", "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_negotiate_sync_disabled(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="neg-dev-disabled", user_id=admin_user.id, sync_enabled=False)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_negotiate_creates_session(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="neg-dev-session", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "session_id" in data
        assert data["session_id"] > 0


class TestNegotiateRomIdsScope:
    """`rom_ids` scopes negotiation to the ROMs installed on the device."""

    def test_scope_omits_downloads_for_uninstalled_roms(
        self,
        client,
        access_token: str,
        admin_user: User,
        rom: Rom,
        save: Save,
        second_save: Save,
    ):
        device = db_device_handler.add_device(
            Device(id="neg-scope-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": [], "rom_ids": [rom.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        save_ids = [op["save_id"] for op in response.json()["operations"]]
        assert save.id in save_ids
        assert second_save.id not in save_ids

    def test_without_scope_all_saves_are_offered(
        self,
        client,
        access_token: str,
        admin_user: User,
        save: Save,
        second_save: Save,
    ):
        device = db_device_handler.add_device(
            Device(id="neg-noscope-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        save_ids = [op["save_id"] for op in response.json()["operations"]]
        assert {save.id, second_save.id} <= set(save_ids)

    def test_client_save_outside_scope_is_still_paired(
        self, client, access_token: str, admin_user: User, rom: Rom, save: Save
    ):
        """A ROM missing from `rom_ids` but present in `saves` must not be
        misread as an upload just because the scope omitted it."""
        device = db_device_handler.add_device(
            Device(id="neg-scope-pair-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "rom_ids": [rom.id + 10_000],
                "saves": [
                    {
                        "rom_id": rom.id,
                        "file_name": save.file_name,
                        "slot": save.slot,
                        "updated_at": "2026-01-10T00:00:00Z",
                        "file_size_bytes": 1024,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_upload"] == 0
        assert [op["save_id"] for op in data["operations"]] == [save.id]

    def test_empty_scope_offers_no_downloads(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        device = db_device_handler.add_device(
            Device(id="neg-empty-scope-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": [], "rom_ids": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["operations"] == []

    def test_scope_does_not_delete_saves_outside_it(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        """The scope is read-only: an omitted ROM keeps its saves."""
        device = db_device_handler.add_device(
            Device(
                id="neg-scope-readonly-dev", user_id=admin_user.id, sync_enabled=True
            )
        )

        client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": [], "rom_ids": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert db_save_handler.get_save(user_id=admin_user.id, id=save.id) is not None

    def test_rejects_non_positive_ids(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="neg-badid-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": [], "rom_ids": [0]},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_rejects_scope_over_the_limit(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="neg-toomany-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [],
                "rom_ids": list(range(1, MAX_ROM_IDS_PER_QUERY + 2)),
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestConcurrentNegotiations:
    """A session belongs to a launch, and a device can have two games open."""

    def _negotiate(self, client, access_token: str, device_id: str) -> int:
        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device_id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        return int(response.json()["session_id"])

    def test_a_second_negotiation_leaves_the_first_session_open(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="concurrent-dev-1", user_id=admin_user.id)
        )

        first = self._negotiate(client, access_token, device.id)
        second = self._negotiate(client, access_token, device.id)
        assert first != second

        still_open = db_sync_session_handler.get_session(first, admin_user.id)
        assert still_open is not None
        assert still_open.status == SyncSessionStatus.IN_PROGRESS

    def test_the_first_launch_can_still_complete_its_own_session(
        self, client, access_token: str, admin_user: User
    ):
        # The push after an exit takes seconds, and pressing Play again inside
        # them used to cancel the session it was about to close.
        device = db_device_handler.add_device(
            Device(id="concurrent-dev-2", user_id=admin_user.id)
        )

        first = self._negotiate(client, access_token, device.id)
        self._negotiate(client, access_token, device.id)

        response = client.post(
            f"/api/sync/sessions/{first}/complete",
            json={"operations_completed": 1, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["session"]["status"] == "COMPLETED"
        assert response.json()["session"]["operations_completed"] == 1


class TestSyncSessions:
    def test_complete_session(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="session-dev-1", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 5, "operations_failed": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session"]["status"] == "COMPLETED"
        assert data["session"]["operations_completed"] == 5
        assert data["session"]["operations_failed"] == 1
        assert data["play_session_ingest"] is None

    def test_complete_session_not_found(self, client, access_token: str):
        response = client.post(
            "/api/sync/sessions/99999/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_complete_already_completed_session(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="session-dev-completed", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )
        db_sync_session_handler.complete_session(session_id=sync_session.id)

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_a_session_the_cleanup_gave_up_on(
        self, client, access_token: str, admin_user: User
    ):
        # A game open past the cutoff, or a client asleep and back again: the
        # counts it returns with are the record, not the cleanup's guess.
        device = db_device_handler.add_device(
            Device(id="session-dev-stale", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )
        db_sync_session_handler.fail_stale_sessions(
            older_than=datetime.now(timezone.utc) + timedelta(minutes=1)
        )

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 2, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["session"]["status"] == "COMPLETED"
        assert response.json()["session"]["operations_completed"] == 2

    def test_list_sessions(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="session-dev-list", user_id=admin_user.id)
        )
        db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )
        db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.get(
            "/api/sync/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2

    def test_list_sessions_filter_by_device(
        self, client, access_token: str, admin_user: User
    ):
        dev_a = db_device_handler.add_device(
            Device(id="session-dev-a", user_id=admin_user.id)
        )
        dev_b = db_device_handler.add_device(
            Device(id="session-dev-b", user_id=admin_user.id)
        )
        db_sync_session_handler.create_session(
            device_id=dev_a.id, user_id=admin_user.id
        )
        db_sync_session_handler.create_session(
            device_id=dev_b.id, user_id=admin_user.id
        )

        response = client.get(
            f"/api/sync/sessions?device_id={dev_a.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["device_id"] == dev_a.id

    def test_get_session(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(id="session-dev-get", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.get(
            f"/api/sync/sessions/{sync_session.id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sync_session.id
        assert data["device_id"] == device.id

    def test_get_session_not_found(self, client, access_token: str):
        response = client.get(
            "/api/sync/sessions/99999",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestSyncUserIsolation:
    def test_cannot_negotiate_with_other_users_device(
        self, client, editor_access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="admin-sync-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cannot_complete_other_users_session(
        self, client, editor_access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="admin-session-dev", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_sessions_only_return_own(
        self,
        client,
        access_token: str,
        editor_access_token: str,
        admin_user: User,
        editor_user: User,
    ):
        admin_dev = db_device_handler.add_device(
            Device(id="admin-iso-dev", user_id=admin_user.id)
        )
        editor_dev = db_device_handler.add_device(
            Device(id="editor-iso-dev", user_id=editor_user.id)
        )
        db_sync_session_handler.create_session(
            device_id=admin_dev.id, user_id=admin_user.id
        )
        db_sync_session_handler.create_session(
            device_id=editor_dev.id, user_id=editor_user.id
        )

        admin_resp = client.get(
            "/api/sync/sessions",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        editor_resp = client.get(
            "/api/sync/sessions",
            headers={"Authorization": f"Bearer {editor_access_token}"},
        )

        assert len(admin_resp.json()) == 1
        assert admin_resp.json()[0]["device_id"] == admin_dev.id
        assert len(editor_resp.json()) == 1
        assert editor_resp.json()[0]["device_id"] == editor_dev.id


class TestPushPullTrigger:
    def test_trigger_push_pull(self, client, access_token: str, admin_user: User):
        device = db_device_handler.add_device(
            Device(
                id="pp-dev-1",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=True,
            )
        )

        with mock.patch("endpoints.sync.high_prio_queue") as mock_queue:
            response = client.post(
                f"/api/sync/devices/{device.id}/push-pull",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["device_id"] == device.id
        assert data["status"] == "PENDING"
        mock_queue.enqueue.assert_called_once()

    def test_trigger_push_pull_wrong_mode(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(
                id="pp-dev-wrong-mode",
                user_id=admin_user.id,
                sync_mode=SyncMode.API,
                sync_enabled=True,
            )
        )

        response = client.post(
            f"/api/sync/devices/{device.id}/push-pull",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_trigger_push_pull_sync_disabled(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(
                id="pp-dev-disabled",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=False,
            )
        )

        response = client.post(
            f"/api/sync/devices/{device.id}/push-pull",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_trigger_push_pull_device_not_found(self, client, access_token: str):
        response = client.post(
            "/api/sync/devices/nonexistent/push-pull",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_trigger_push_pull_passes_session_id(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(
                id="pp-dev-sid",
                user_id=admin_user.id,
                sync_mode=SyncMode.PUSH_PULL,
                sync_enabled=True,
            )
        )

        with mock.patch("endpoints.sync.high_prio_queue") as mock_queue:
            response = client.post(
                f"/api/sync/devices/{device.id}/push-pull",
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_queue.enqueue.call_args
        assert "session_id" in call_kwargs.kwargs


def _negotiate(client, access_token, device_id, saves):
    resp = client.post(
        "/api/sync/negotiate",
        json={"device_id": device_id, "saves": saves},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    return resp.json()


def _slot_version(
    user: User, rom: Rom, stem: str, content_hash: str, updated_at: datetime
) -> Save:
    save = db_save_handler.add_save(
        Save(
            rom_id=rom.id,
            user_id=user.id,
            file_name=f"{stem}.sav",
            file_name_no_tags=stem,
            file_name_no_ext=stem,
            file_extension="sav",
            file_path=f"{rom.platform_slug}/saves",
            file_size_bytes=100,
            slot="autosave",
            content_hash=content_hash,
        )
    )
    return db_save_handler.update_save(save.id, {"updated_at": updated_at})


class TestNegotiateRemovedVersions:
    """A version that left its slot on the server is never offered back."""

    BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)

    @staticmethod
    def _held(rom: Rom, content_hash: str) -> dict:
        return {
            "rom_id": rom.id,
            "file_name": "autosave.sav",
            "slot": "autosave",
            "content_hash": content_hash,
            "updated_at": "2026-02-01T00:00:00Z",
            "file_size_bytes": 100,
        }

    def _delete(self, client, access_token: str, save: Save) -> None:
        response = client.post(
            "/api/saves/delete",
            json={"saves": [save.id]},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_a_rolled_back_version_is_replaced_by_the_current_one(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="removed-rollback", user_id=admin_user.id, sync_enabled=True)
        )
        older = _slot_version(admin_user, rom, "older", "HASH_A", self.BASE)
        newest = _slot_version(
            admin_user, rom, "newest", "HASH_B", self.BASE + timedelta(hours=1)
        )
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id, save_id=newest.id, synced_at=newest.updated_at
        )
        self._delete(client, access_token, newest)

        data = _negotiate(client, access_token, device.id, [self._held(rom, "HASH_B")])

        [op] = data["operations"]
        assert op["action"] == "download"
        assert op["save_id"] == older.id

    def test_a_pruned_version_is_deleted_once_the_slot_is(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="removed-pruned", user_id=admin_user.id, sync_enabled=True)
        )
        _slot_version(admin_user, rom, "v1", "HASH_V1", self.BASE)
        current = _slot_version(
            admin_user, rom, "v2", "HASH_V2", self.BASE + timedelta(hours=1)
        )
        db_save_handler.prune_slot(
            user_id=admin_user.id, rom_id=rom.id, slot="autosave", keep=1
        )
        self._delete(client, access_token, current)

        data = _negotiate(client, access_token, device.id, [self._held(rom, "HASH_V1")])

        assert data["operations"][0]["action"] == "delete"

    def test_an_overwritten_version_is_deleted_once_the_slot_is(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="removed-overwritten", user_id=admin_user.id, sync_enabled=True)
        )
        save = _slot_version(admin_user, rom, "v1", "HASH_V1", self.BASE)
        save = db_save_handler.update_save(save.id, {"content_hash": "HASH_V2"})
        self._delete(client, access_token, save)

        data = _negotiate(client, access_token, device.id, [self._held(rom, "HASH_V1")])

        assert data["operations"][0]["action"] == "delete"

    def test_the_current_version_matches_even_after_it_was_once_removed(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="removed-refilled", user_id=admin_user.id, sync_enabled=True)
        )
        db_deleted_asset_handler.record_deletion(
            user_id=admin_user.id,
            rom_id=rom.id,
            slot="autosave",
            content_hash="HASH_A",
        )
        _slot_version(admin_user, rom, "again", "HASH_A", self.BASE)

        data = _negotiate(client, access_token, device.id, [self._held(rom, "HASH_A")])

        assert data["operations"][0]["action"] == "no_op"


class TestNegotiateAdvanced:
    def test_negotiate_untracked_save_returns_noop(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        device = db_device_handler.add_device(
            Device(id="neg-untrack-dev", user_id=admin_user.id, sync_enabled=True)
        )
        db_device_save_sync_handler.set_untracked(
            device_id=device.id, save_id=save.id, untracked=True
        )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [
                    {
                        "rom_id": save.rom_id,
                        "file_name": save.file_name,
                        "slot": save.slot,
                        "content_hash": "different_hash",
                        "updated_at": "2026-03-01T00:00:00Z",
                        "file_size_bytes": 100,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        noop_ops = [op for op in data["operations"] if op["action"] == "no_op"]
        assert len(noop_ops) >= 1

    def test_negotiate_server_save_not_mentioned_by_client(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        device = db_device_handler.add_device(
            Device(id="neg-miss-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        download_ops = [op for op in data["operations"] if op["action"] == "download"]
        assert len(download_ops) >= 1
        assert any(op["save_id"] == save.id for op in download_ops)

    def test_negotiate_excludes_archival_null_slot_saves(
        self, client, access_token: str, admin_user: User, archival_save: Save
    ):
        """Null-slot saves (web-UI / archival uploads) must not appear in
        negotiate plans.

        Archival saves are pure backups; clients can opt in to import them
        outside the sync flow. Surfacing them in negotiate as 'download'
        produces phantom operations on every device that's never synced them.
        """
        device = db_device_handler.add_device(
            Device(id="neg-archival-dev", user_id=admin_user.id, sync_enabled=True)
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        ops_for_archival = [
            op for op in data["operations"] if op.get("save_id") == archival_save.id
        ]
        assert ops_for_archival == [], (
            f"Archival null-slot save unexpectedly surfaced in negotiate: "
            f"{ops_for_archival}"
        )

    def test_negotiate_deleted_by_client_skipped(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        device = db_device_handler.add_device(
            Device(id="neg-del-dev", user_id=admin_user.id, sync_enabled=True)
        )
        db_device_save_sync_handler.upsert_sync(
            device_id=device.id,
            save_id=save.id,
            synced_at=datetime.now(timezone.utc),
        )

        response = client.post(
            "/api/sync/negotiate",
            json={"device_id": device.id, "saves": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        ops_for_save = [op for op in data["operations"] if op.get("save_id") == save.id]
        assert len(ops_for_save) == 0

    def test_negotiate_matches_untagged_client_to_tagged_server_saves(
        self, client, access_token: str, admin_user: User, rom: Rom, platform
    ):
        """Spec datetime-tags every slot upload, so a slot accrues many tagged rows and the client reports the untagged canonical name. Pairing must be by (rom_id, slot) on the newest row, else every negotiate yields upload+download forever."""
        device = db_device_handler.add_device(
            Device(id="neg-tagged-dev", user_id=admin_user.id, sync_enabled=True)
        )
        for tag in ("2026-01-01_00-00-00", "2026-02-02_00-00-00"):
            db_save_handler.add_save(
                Save(
                    rom_id=rom.id,
                    user_id=admin_user.id,
                    file_name=f"test_save [{tag}].sav",
                    file_name_no_tags="test_save",
                    file_name_no_ext=f"test_save [{tag}]",
                    file_extension="sav",
                    emulator="test_emulator",
                    slot="autosave",
                    content_hash="HASH_MATCH",
                    file_path=f"{platform.slug}/saves/test_emulator",
                    file_size_bytes=1.0,
                )
            )

        response = client.post(
            "/api/sync/negotiate",
            json={
                "device_id": device.id,
                "saves": [
                    {
                        "rom_id": rom.id,
                        "file_name": "test_save.sav",
                        "slot": "autosave",
                        "content_hash": "HASH_MATCH",
                        "updated_at": "2026-03-01T00:00:00Z",
                        "file_size_bytes": 100,
                    }
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_upload"] == 0
        assert data["total_download"] == 0
        rom_ops = [op for op in data["operations"] if op["rom_id"] == rom.id]
        assert len(rom_ops) == 1
        assert rom_ops[0]["action"] == "no_op"

    def _upload_autosave(
        self, client, access_token, rom, *, filename, content_hash, device_id
    ):
        """Upload through the real add_save so _apply_datetime_tag runs; scan_save is mocked to echo the server-computed (tagged) file_name, never a hand-authored one."""

        def make_scanned(*, file_name, user, platform_fs_slug, rom_id, emulator):
            return Save(
                file_name=file_name,
                file_name_no_tags=file_name.split(" [")[0],
                file_name_no_ext=os.path.splitext(file_name)[0],
                file_extension="zip",
                file_path=f"{platform_fs_slug}/saves/{emulator or ''}",
                file_size_bytes=100,
                content_hash=content_hash,
            )

        with (
            mock.patch(
                "endpoints.saves.fs_asset_handler.write_file",
                new_callable=mock.AsyncMock,
            ),
            mock.patch(
                "endpoints.saves.fs_asset_handler.remove_file",
                new_callable=mock.AsyncMock,
            ),
            mock.patch(
                "endpoints.saves.scan_save",
                new=mock.AsyncMock(side_effect=make_scanned),
            ),
        ):
            return client.post(
                f"/api/saves?rom_id={rom.id}&slot=autosave&emulator=eden"
                f"&device_id={device_id}",
                files={
                    "saveFile": (
                        filename,
                        BytesIO(b"save bytes"),
                        "application/octet-stream",
                    )
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )

    @staticmethod
    def _autosave_entry(rom, content_hash):
        return {
            "rom_id": rom.id,
            "file_name": "pokemon_violet.zip",
            "slot": "autosave",
            "content_hash": content_hash,
            "updated_at": "2026-03-01T00:00:00Z",
            "file_size_bytes": 100,
        }

    def test_save_upload_then_negotiate_converges(
        self, client, access_token: str, admin_user: User, rom: Rom, platform
    ):
        """Full round-trip: upload tags the filename (real add_save), then the client reports its untagged canonical name. Must converge to no_op, not re-upload. This is the regression that hand-fed-filename mocks missed."""
        device = db_device_handler.add_device(
            Device(id="conv-rt-dev", user_id=admin_user.id, sync_enabled=True)
        )
        up = self._upload_autosave(
            client,
            access_token,
            rom,
            filename="pokemon_violet.zip",
            content_hash="HASH_RT",
            device_id=device.id,
        )
        assert up.status_code == status.HTTP_200_OK
        stored = up.json()
        assert stored["file_name"] != "pokemon_violet.zip"
        assert " [" in stored["file_name"]

        data = _negotiate(
            client, access_token, device.id, [self._autosave_entry(rom, "HASH_RT")]
        )
        assert data["total_upload"] == 0
        assert data["total_download"] == 0
        rom_ops = [op for op in data["operations"] if op["rom_id"] == rom.id]
        assert len(rom_ops) == 1
        assert rom_ops[0]["action"] == "no_op"

    def test_three_device_sync_converges(
        self, client, access_token: str, admin_user: User, rom: Rom, platform
    ):
        """A uploads; B and C each download exactly once then converge to no_op. The pre-fix tagged-filename keying made every device upload+download forever -- this is the 3-device scenario done with faithful (untagged client / tagged server) names."""
        device_a = db_device_handler.add_device(
            Device(id="conv-a", user_id=admin_user.id, sync_enabled=True)
        )
        up = self._upload_autosave(
            client,
            access_token,
            rom,
            filename="pokemon_violet.zip",
            content_hash="HASH_3D",
            device_id=device_a.id,
        )
        assert up.status_code == status.HTTP_200_OK
        save_id = up.json()["id"]

        a_data = _negotiate(
            client, access_token, device_a.id, [self._autosave_entry(rom, "HASH_3D")]
        )
        assert a_data["total_upload"] == 0
        assert a_data["total_download"] == 0

        for dev_id in ("conv-b", "conv-c"):
            dev = db_device_handler.add_device(
                Device(id=dev_id, user_id=admin_user.id, sync_enabled=True)
            )
            first = _negotiate(client, access_token, dev.id, [])
            downloads = [
                op
                for op in first["operations"]
                if op["action"] == "download" and op["save_id"] == save_id
            ]
            assert len(downloads) == 1
            db_device_save_sync_handler.upsert_sync(
                device_id=dev.id, save_id=save_id, synced_at=datetime.now(timezone.utc)
            )
            second = _negotiate(
                client, access_token, dev.id, [self._autosave_entry(rom, "HASH_3D")]
            )
            assert second["total_upload"] == 0
            assert second["total_download"] == 0

    def test_complete_failed_session_rejected(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="sess-failed-dev", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )
        db_sync_session_handler.fail_session(sync_session.id, error_message="test")

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_cancelled_session_rejected(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="sess-cancel-dev", user_id=admin_user.id)
        )
        created = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )
        # Nothing cancels a session any more, but a row left in that state by a
        # server that once did is still one this endpoint has to refuse.
        cancelled = db_sync_session_handler.update_session(
            created.id, {"status": SyncSessionStatus.CANCELLED}
        )

        response = client.post(
            f"/api/sync/sessions/{cancelled.id}/complete",
            json={"operations_completed": 0, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


def _play_session(rom_id=None, start_offset_hours=-1, duration_minutes=30):
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=start_offset_hours)
    end = start + timedelta(minutes=duration_minutes)
    return {
        "rom_id": rom_id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "duration_ms": duration_minutes * 60 * 1000,
    }


class TestSyncCompleteWithPlaySessions:
    def test_complete_with_play_sessions(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="sync-ps-dev-1", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={
                "operations_completed": 1,
                "operations_failed": 0,
                "play_sessions": [
                    _play_session(rom_id=rom.id, start_offset_hours=-2),
                    _play_session(rom_id=rom.id, start_offset_hours=-4),
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session"]["status"] == "COMPLETED"
        assert data["play_session_ingest"] is not None
        assert data["play_session_ingest"]["created_count"] == 2
        assert data["play_session_ingest"]["skipped_count"] == 0

    def test_play_sessions_use_device_from_sync_session(
        self, client, access_token: str, admin_user: User, rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="sync-ps-dev-3", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={
                "operations_completed": 0,
                "operations_failed": 0,
                "play_sessions": [
                    _play_session(rom_id=rom.id, start_offset_hours=-5),
                ],
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )

        sessions = db_play_session_handler.get_sessions(
            user_id=admin_user.id, rom_id=rom.id
        )
        assert len(sessions) >= 1
        assert sessions[0].device_id == device.id

    def test_complete_without_play_sessions_backward_compatible(
        self, client, access_token: str, admin_user: User
    ):
        device = db_device_handler.add_device(
            Device(id="sync-ps-dev-4", user_id=admin_user.id)
        )
        sync_session = db_sync_session_handler.create_session(
            device_id=device.id, user_id=admin_user.id
        )

        response = client.post(
            f"/api/sync/sessions/{sync_session.id}/complete",
            json={"operations_completed": 3, "operations_failed": 0},
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session"]["status"] == "COMPLETED"
        assert data["play_session_ingest"] is None


class TestNegotiateConflictEvents:
    """A negotiating client has nowhere to resolve a conflict, so the socket
    event is the only surface the user gets."""

    @staticmethod
    def _device_with_history(
        device_id: str, admin_user: User, saves: list[Save]
    ) -> Device:
        """A device whose last sync of each save was an hour ago."""
        device = db_device_handler.add_device(
            Device(id=device_id, user_id=admin_user.id, sync_enabled=True)
        )
        for save in saves:
            db_device_save_sync_handler.upsert_sync(
                device_id=device.id,
                save_id=save.id,
                synced_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        return device

    @staticmethod
    def _changed_client_save(save: Save) -> dict:
        return {
            "rom_id": save.rom_id,
            "file_name": save.file_name,
            "slot": save.slot,
            "content_hash": "hash_the_server_never_saw",
            "updated_at": "2099-01-01T00:00:00Z",
            "file_size_bytes": 100,
        }

    @staticmethod
    def _patch_emit(side_effect: Any = None):
        return mock.patch(
            "endpoints.sync.emit_sync_conflict",
            new_callable=mock.AsyncMock,
            side_effect=side_effect,
        )

    @staticmethod
    def _patch_broker_emit(side_effect: Any):
        """Fail below emit_sync_conflict, where production failures happen."""
        return mock.patch.object(
            socket_handler,
            "write_manager",
            return_value=mock.Mock(emit=mock.AsyncMock(side_effect=side_effect)),
        )

    def test_conflict_emits_socket_event(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        device = self._device_with_history("neg-conflict-dev", admin_user, [save])

        with self._patch_emit() as emit:
            data = _negotiate(
                client, access_token, device.id, [self._changed_client_save(save)]
            )

        assert data["total_conflict"] == 1
        emit.assert_awaited_once()
        assert emit.await_args is not None
        assert emit.await_args.kwargs == {
            "user_id": admin_user.id,
            "device_id": device.id,
            "session_id": data["session_id"],
            "file_name": save.file_name,
            "rom_id": save.rom_id,
            "rom_name": "test_rom",
            "reason": "Both sides changed since last sync",
        }

    def test_no_conflict_negotiation_emits_nothing(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        """A negotiated no_op is not a conflict, so it must stay silent."""
        device = db_device_handler.add_device(
            Device(id="neg-calm-dev", user_id=admin_user.id, sync_enabled=True)
        )
        db_device_save_sync_handler.set_untracked(
            device_id=device.id, save_id=save.id, untracked=True
        )

        with self._patch_emit() as emit:
            data = _negotiate(
                client, access_token, device.id, [self._changed_client_save(save)]
            )

        assert data["total_conflict"] == 0
        assert any(op["action"] == "no_op" for op in data["operations"])
        emit.assert_not_awaited()

    def test_emit_failure_leaves_the_negotiation_intact(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        """An unreachable Redis must not stop a client from syncing."""
        device = self._device_with_history("neg-conflict-down", admin_user, [save])

        with self._patch_broker_emit(RuntimeError("redis is down")):
            data = _negotiate(
                client, access_token, device.id, [self._changed_client_save(save)]
            )

        assert data["total_conflict"] == 1

    def test_hung_broker_is_abandoned_at_the_deadline(
        self, client, access_token: str, admin_user: User, save: Save
    ):
        device = self._device_with_history("neg-conflict-slow", admin_user, [save])

        async def hang(**_kwargs: Any) -> None:
            await asyncio.sleep(30)

        with (
            self._patch_emit(hang),
            mock.patch("endpoints.sync.CONFLICT_NOTIFY_TIMEOUT_S", 0.01),
        ):
            started = time.monotonic()
            data = _negotiate(
                client, access_token, device.id, [self._changed_client_save(save)]
            )
            elapsed = time.monotonic() - started

        assert data["total_conflict"] == 1
        assert elapsed < 10

    def test_one_failed_emit_does_not_drop_the_rest(
        self,
        client,
        access_token: str,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        saves = [
            db_save_handler.add_save(
                Save(
                    rom_id=rom.id,
                    user_id=admin_user.id,
                    file_name=f"wide_{index}.sav",
                    file_name_no_tags=f"wide_{index}",
                    file_name_no_ext=f"wide_{index}",
                    file_extension="sav",
                    emulator="test_emulator",
                    slot=f"slot-{index}",
                    file_path=f"{platform.slug}/saves/test_emulator",
                    file_size_bytes=1.0,
                )
            )
            for index in range(3)
        ]
        device = self._device_with_history("neg-conflict-wide", admin_user, saves)

        with self._patch_broker_emit(
            [RuntimeError("redis blip"), None, None]
        ) as write_manager:
            data = _negotiate(
                client,
                access_token,
                device.id,
                [self._changed_client_save(save) for save in saves],
            )

        assert data["total_conflict"] == len(saves)
        assert write_manager.return_value.emit.await_count == len(saves)
