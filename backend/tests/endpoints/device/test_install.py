import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from tests.factories import make_device_token, make_platform, make_rom

from endpoints.device import install as device_install
from endpoints.responses.device.install import InstallRequestSchema, InstallStatus
from handler.database import db_device_handler, db_rom_handler
from handler.database.base_handler import sync_session
from handler.device_install import device_install_handler
from handler.redis_handler import sync_cache
from models.device import Device
from models.notification import NotificationKind, NotificationLevel
from models.permission import HiddenEntity, PermEntity
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User

REMOTE_INSTALL = {"remote_install": True}


@pytest.fixture(autouse=True)
def emits(mocker):
    return {
        "queued": mocker.patch.object(
            device_install, "emit_install_queued", AsyncMock()
        ),
        "cancelled": mocker.patch.object(
            device_install, "emit_install_cancelled", AsyncMock()
        ),
        "updated": mocker.patch.object(
            device_install, "emit_install_updated", AsyncMock()
        ),
        "notify": mocker.patch.object(device_install, "notify", AsyncMock()),
    }


@pytest.fixture
def device(admin_user: User) -> Device:
    return db_device_handler.add_device(
        Device(
            id="dev-1",
            user_id=admin_user.id,
            name="Handheld",
            capabilities=REMOTE_INSTALL,
        )
    )


@pytest.fixture
def other_device(admin_user: User) -> Device:
    return db_device_handler.add_device(
        Device(
            id="dev-2",
            user_id=admin_user.id,
            name="TV box",
            capabilities=REMOTE_INSTALL,
        )
    )


@pytest.fixture
def device_headers(admin_user: User, device: Device) -> dict[str, str]:
    _, raw_token = make_device_token(admin_user, device.id)
    return {"Authorization": f"Bearer {raw_token}"}


@pytest.fixture
def editor_device(editor_user: User) -> Device:
    return db_device_handler.add_device(
        Device(
            id="dev-editor",
            user_id=editor_user.id,
            name="Editor handheld",
            capabilities=REMOTE_INSTALL,
        )
    )


def _hide_rom(rom: Rom, user: User) -> None:
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=PermEntity.ROMS, entity_id=rom.id, user_id=user.id))


def _add_file(
    rom: Rom,
    file_name: str,
    category: RomFileCategory | None,
    missing: bool = False,
) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=file_name,
            file_path=rom.fs_path,
            file_size_bytes=1,
            category=category,
            missing_from_fs=missing,
        )
    )


@pytest.fixture
def rom_files(rom: Rom) -> dict[str, RomFile]:
    return {
        "game": _add_file(rom, "game.bin", RomFileCategory.GAME),
        "update": _add_file(rom, "update.nsp", RomFileCategory.UPDATE),
        "soundtrack": _add_file(rom, "ost.flac", RomFileCategory.SOUNDTRACK),
        "manual": _add_file(rom, "manual.pdf", RomFileCategory.MANUAL),
        "gone": _add_file(rom, "gone.bin", RomFileCategory.GAME, missing=True),
    }


def _create(client, headers, rom_id: int, device_id: str = "dev-1"):
    return client.post(
        f"/api/devices/{device_id}/installs",
        json={"rom_id": rom_id},
        headers=headers,
    )


def _claim(client, headers, device_id: str = "dev-1"):
    return client.post(f"/api/devices/{device_id}/installs/claim", headers=headers)


def _report(client, device_headers, request_id: str, new_status: str, **body):
    return client.put(
        f"/api/devices/dev-1/installs/{request_id}",
        json={"status": new_status, **body},
        headers=device_headers,
    )


def _cancel(client, headers, request_id: str, device_id: str = "dev-1"):
    return client.delete(
        f"/api/devices/{device_id}/installs/{request_id}", headers=headers
    )


def _stored(request_id: str) -> InstallRequestSchema | None:
    return asyncio.run(device_install_handler.get(request_id))


def _live_on_device(device_id: str = "dev-1") -> list[InstallRequestSchema]:
    return asyncio.run(device_install_handler.list_for_device(device_id))


def _taken(client, headers, device_headers, rom_id: int) -> str:
    request_id = str(_create(client, headers, rom_id).json()["id"])
    assert _claim(client, device_headers).status_code == status.HTTP_200_OK
    return request_id


class TestCreate:
    def test_queues_the_installable_files_and_signals_the_device(
        self, client, headers, device, rom, rom_files, emits
    ):
        response = _create(client, headers, rom.id)

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["status"] == "pending"
        assert body["device_id"] == device.id
        assert body["file_ids"] == sorted(
            [rom_files["game"].id, rom_files["update"].id]
        )
        emits["queued"].assert_awaited_once()
        assert emits["queued"].await_args.args[0].id == body["id"]

    def test_a_second_tick_returns_the_request_already_queued(
        self, client, headers, device, rom, rom_files, emits
    ):
        first = _create(client, headers, rom.id).json()

        response = _create(client, headers, rom.id)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == first["id"]
        emits["queued"].assert_awaited_once()

    def test_rejects_a_rom_with_nothing_installable(self, client, headers, device, rom):
        _add_file(rom, "ost.flac", RomFileCategory.SOUNDTRACK)
        _add_file(rom, "gone.bin", RomFileCategory.GAME, missing=True)

        response = _create(client, headers, rom.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rejects_a_rom_missing_from_the_filesystem(
        self, client, headers, device, rom, rom_files, emits
    ):
        db_rom_handler.update_rom(rom.id, {"missing_from_fs": True})

        response = _create(client, headers, rom.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        emits["queued"].assert_not_awaited()

    def test_rejects_an_excluded_platform(self, client, headers, device):
        platform = make_platform("win", name="Windows")
        rom = make_rom(platform, "setup", fs_extension="exe")
        _add_file(rom, "setup.exe", RomFileCategory.GAME)

        response = _create(client, headers, rom.id)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_a_hidden_rom_is_not_found(
        self, client, editor_headers, editor_device, editor_user, rom, rom_files, emits
    ):
        _hide_rom(rom, editor_user)

        response = _create(client, editor_headers, rom.id, device_id=editor_device.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        emits["queued"].assert_not_awaited()

    def test_another_users_device_is_not_found(
        self, client, editor_headers, device, rom, rom_files
    ):
        response = _create(client, editor_headers, rom.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.parametrize(
        "capabilities", [None, {}, {"remote_install": False}, {"sync": True}]
    )
    def test_rejects_a_device_that_does_not_accept_remote_installs(
        self, client, headers, admin_user, rom, rom_files, emits, capabilities
    ):
        db_device_handler.add_device(
            Device(
                id="dev-sync",
                user_id=admin_user.id,
                name="Sync only",
                capabilities=capabilities,
            )
        )

        response = _create(client, headers, rom.id, device_id="dev-sync")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        emits["queued"].assert_not_awaited()

    def test_a_device_deleted_during_the_create_keeps_no_request(
        self, mocker, client, headers, admin_user, device, rom, rom_files, emits
    ):
        real_create = device_install_handler.create

        async def create_then_delete_device(
            user_id: int, device_id: str, rom_id: int, file_ids: list[int]
        ) -> tuple[InstallRequestSchema, bool]:
            created = await real_create(
                user_id=user_id, device_id=device_id, rom_id=rom_id, file_ids=file_ids
            )
            db_device_handler.delete_device(device_id=device_id, user_id=user_id)
            return created

        mocker.patch.object(
            device_install_handler, "create", side_effect=create_then_delete_device
        )

        response = _create(client, headers, rom.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert _live_on_device() == []
        emits["queued"].assert_not_awaited()

    def test_is_not_found_while_disabled(
        self, mocker, client, headers, device, rom, rom_files
    ):
        mocker.patch.object(device_install, "DEVICE_INSTALL_ENABLED", False)

        response = _create(client, headers, rom.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestOnline:
    def test_lists_the_callers_devices_holding_a_socket(
        self, client, headers, admin_user: User, editor_user: User
    ):
        for device_id, user in (
            ("dev-online", admin_user),
            ("dev-offline", admin_user),
            ("dev-editor", editor_user),
        ):
            db_device_handler.add_device(Device(id=device_id, user_id=user.id))
        sync_cache.sadd("device_presence:dev-online", "sid-1")
        sync_cache.sadd("device_presence:dev-editor", "sid-2")

        response = client.get("/api/devices/online", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == ["dev-online"]

    def test_a_device_that_just_claimed_is_online_without_a_socket(
        self, client, headers, device_headers, device
    ):
        _claim(client, device_headers)

        response = client.get("/api/devices/online", headers=headers)

        assert response.json() == ["dev-1"]

    def test_is_not_found_while_disabled(self, mocker, client, headers):
        mocker.patch.object(device_install, "DEVICE_INSTALL_ENABLED", False)

        response = client.get("/api/devices/online", headers=headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestList:
    def test_the_device_reads_its_live_requests(
        self, client, headers, device_headers, device, rom, second_rom, rom_files
    ):
        taken = _taken(client, headers, device_headers, rom.id)
        _add_file(second_rom, "other.bin", RomFileCategory.GAME)
        pending = _create(client, headers, second_rom.id).json()["id"]

        response = client.get("/api/devices/dev-1/installs", headers=device_headers)

        assert response.status_code == status.HTTP_200_OK
        assert [(r["id"], r["status"]) for r in response.json()] == [
            (taken, "taken"),
            (pending, "pending"),
        ]

    def test_a_device_token_cannot_read_another_device(
        self, client, device_headers, other_device
    ):
        response = client.get("/api/devices/dev-2/installs", headers=device_headers)

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestClaim:
    def test_takes_and_returns_the_pending_requests(
        self, client, headers, device_headers, device, rom, rom_files, emits
    ):
        created = _create(client, headers, rom.id).json()

        response = _claim(client, device_headers)

        assert response.status_code == status.HTTP_200_OK
        assert [(r["id"], r["status"]) for r in response.json()] == [
            (created["id"], "taken")
        ]
        stored = _stored(created["id"])
        assert stored is not None and stored.status == InstallStatus.TAKEN
        assert emits["updated"].await_args.args[0].status == "taken"

    def test_a_second_claim_returns_the_taken_request_without_signalling_it(
        self, client, headers, device_headers, device, rom, rom_files, emits
    ):
        request_id = _create(client, headers, rom.id).json()["id"]
        _claim(client, device_headers)
        emits["updated"].reset_mock()

        response = _claim(client, device_headers)

        assert response.status_code == status.HTTP_200_OK
        assert [(r["id"], r["status"]) for r in response.json()] == [
            (request_id, "taken")
        ]
        emits["updated"].assert_not_awaited()

    def test_a_reported_request_is_not_claimed_again(
        self, client, headers, device_headers, device, rom, rom_files
    ):
        request_id = _taken(client, headers, device_headers, rom.id)
        _report(client, device_headers, request_id, "done")

        response = _claim(client, device_headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_a_cancelled_request_is_never_claimed(
        self, client, headers, device_headers, device, rom, rom_files
    ):
        request_id = _create(client, headers, rom.id).json()["id"]
        _cancel(client, headers, request_id)

        response = _claim(client, device_headers)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_another_devices_token_is_refused(
        self, client, headers, device_headers, device, other_device, rom, rom_files
    ):
        _create(client, headers, rom.id, device_id="dev-2")

        response = _claim(client, device_headers, device_id="dev-2")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_the_web_ui_cannot_claim(self, client, headers, device, rom, rom_files):
        _create(client, headers, rom.id)

        response = _claim(client, headers)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_a_token_that_cannot_download_leaves_requests_pending(
        self, client, headers, admin_user, device, rom, rom_files
    ):
        request_id = _create(client, headers, rom.id).json()["id"]
        _, raw = make_device_token(
            admin_user, device.id, scopes="devices.read devices.write"
        )

        response = _claim(client, {"Authorization": f"Bearer {raw}"})

        assert response.status_code == status.HTTP_403_FORBIDDEN
        stored = _stored(request_id)
        assert stored is not None and stored.status == InstallStatus.PENDING


class TestDeviceReport:
    def test_a_failure_ends_the_request_and_notifies_the_owner(
        self, client, headers, device_headers, admin_user, device, rom, rom_files, emits
    ):
        request_id = _taken(client, headers, device_headers, rom.id)

        response = _report(
            client, device_headers, request_id, "failed", reason="no space"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "failed"
        assert response.json()["reason"] == "no space"
        assert _stored(request_id) is None
        assert _live_on_device() == []
        assert emits["updated"].await_args.args[0].status == "failed"
        emits["notify"].assert_awaited_once()
        user_id, kind, level, data = emits["notify"].await_args.args
        assert user_id == admin_user.id
        assert kind == NotificationKind.DEVICE_INSTALL_FAILED
        assert level == NotificationLevel.ERROR
        assert data["reason"] == "no space"
        assert data["rom_id"] == rom.id
        assert data["device_name"] == "Handheld"

    @pytest.mark.parametrize("outcome", ["done", "already_installed"])
    def test_a_completion_notifies_the_owner(
        self, client, headers, device_headers, device, rom, rom_files, emits, outcome
    ):
        request_id = _taken(client, headers, device_headers, rom.id)

        _report(client, device_headers, request_id, outcome)

        _, kind, level, data = emits["notify"].await_args.args
        assert kind == NotificationKind.DEVICE_INSTALL_COMPLETED
        assert level == NotificationLevel.SUCCESS
        assert data["status"] == outcome

    def test_claiming_a_request_notifies_nobody(
        self, client, headers, device_headers, device, rom, rom_files, emits
    ):
        _taken(client, headers, device_headers, rom.id)

        emits["notify"].assert_not_awaited()

    def test_a_repeated_report_is_not_found_and_notifies_once(
        self, client, headers, device_headers, device, rom, rom_files, emits
    ):
        request_id = _taken(client, headers, device_headers, rom.id)

        first = _report(client, device_headers, request_id, "done")
        again = _report(client, device_headers, request_id, "done")

        assert first.status_code == status.HTTP_200_OK
        assert again.status_code == status.HTTP_404_NOT_FOUND
        emits["notify"].assert_awaited_once()

    def test_a_pending_request_is_a_conflict(
        self, client, headers, device_headers, device, rom, rom_files, emits
    ):
        request_id = _create(client, headers, rom.id).json()["id"]

        response = _report(client, device_headers, request_id, "done")

        assert response.status_code == status.HTTP_409_CONFLICT
        stored = _stored(request_id)
        assert stored is not None and stored.status == InstallStatus.PENDING
        emits["notify"].assert_not_awaited()

    def test_the_web_ui_cannot_report(
        self, client, headers, device_headers, device, rom, rom_files
    ):
        request_id = _taken(client, headers, device_headers, rom.id)

        response = _report(client, headers, request_id, "done")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.parametrize("reported", ["pending", "taken", "cancelled"])
    def test_a_device_cannot_report_a_status_it_does_not_own(
        self, client, headers, device_headers, device, rom, rom_files, reported
    ):
        request_id = _taken(client, headers, device_headers, rom.id)

        response = _report(client, device_headers, request_id, reported)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestCancel:
    @pytest.mark.parametrize("claim", [False, True])
    def test_cancels_a_live_request_and_deletes_it(
        self, client, headers, device_headers, device, rom, rom_files, emits, claim
    ):
        request_id = (
            _taken(client, headers, device_headers, rom.id)
            if claim
            else _create(client, headers, rom.id).json()["id"]
        )

        response = _cancel(client, headers, request_id)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "cancelled"
        assert _stored(request_id) is None
        assert emits["updated"].await_args.args[0].status == "cancelled"
        emits["cancelled"].assert_awaited_once()
        cancelled = emits["cancelled"].await_args
        assert cancelled is not None
        assert cancelled.args[0].id == request_id
        emits["notify"].assert_not_awaited()

    def test_the_device_report_after_a_cancel_is_not_found(
        self, client, headers, device_headers, device, rom, rom_files
    ):
        request_id = _taken(client, headers, device_headers, rom.id)
        _cancel(client, headers, request_id)

        response = _report(client, device_headers, request_id, "done")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_an_ended_request_cannot_be_cancelled(
        self, client, headers, device_headers, device, rom, rom_files
    ):
        request_id = _taken(client, headers, device_headers, rom.id)
        _report(client, device_headers, request_id, "done")

        response = _cancel(client, headers, request_id)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_a_request_on_another_device_path_is_not_found(
        self, client, headers, device, other_device, rom, rom_files
    ):
        request_id = _create(client, headers, rom.id).json()["id"]

        response = _cancel(client, headers, request_id, device_id="dev-2")

        assert response.status_code == status.HTTP_404_NOT_FOUND
