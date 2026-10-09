"""Legacy negotiate and slot uploads on a channel a snapshot client keeps."""

import io
import uuid
import zipfile
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests._zipfile_shim import reload_zipfile
from tests.handler.snapshots.pushes import md5, part, push, save_entry, stored_bytes

from handler.database import (
    db_device_handler,
    db_device_save_sync_handler,
    db_rom_handler,
    db_save_handler,
    db_snapshot_handler,
    db_state_handler,
)
from handler.snapshots import bridge
from handler.snapshots.manifest import Manifest
from handler.snapshots.write import (
    SAVE_PART,
    SnapshotWrite,
    WriteResult,
    state_part,
    write_snapshot,
)
from models.assets import Save, SaveFormat, SaveShape
from models.channel import Channel
from models.device import Device
from models.rom import Rom, RomFile
from models.snapshot import SnapshotKind
from models.user import User

KEPT = b"kept-by-snapshots"
LEGACY = b"legacy-upload"
STATE = b"state-bytes"

pytestmark = pytest.mark.usefixtures("_isolated_assets_dir")


@pytest.fixture
def game_file(rom: Rom) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="game.sfc",
            file_path=rom.fs_path,
            file_size_bytes=1024,
            sha1_hash="c" * 40,
        )
    )


@pytest.fixture
def legacy_device(admin_user: User) -> Device:
    return db_device_handler.add_device(
        Device(id="legacy", user_id=admin_user.id, sync_enabled=True)
    )


def auth(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def snapshot_push(
    user: User,
    rom: Rom,
    rom_file: RomFile,
    fmt: SaveFormat = SaveFormat.NATIVE,
    is_hardcore: bool = False,
    channel_id: uuid.UUID | None = None,
    emulator: str = "snes9x",
    core: str | None = None,
) -> WriteResult:
    states = {} if is_hardcore else {"snes9x": {"auto": md5(STATE)}}
    parts = {SAVE_PART: part(KEPT)}
    if not is_hardcore:
        parts[state_part("snes9x", "auto")] = part(STATE, "game.state")
    return await write_snapshot(
        push(
            user,
            rom,
            rom_file,
            Manifest(
                save=save_entry(KEPT, fmt),
                states=states,
                emulator=emulator,
                core=core,
                is_hardcore=is_hardcore,
            ),
            expected=None,
            channel_id=channel_id,
            parts=parts,
            device_id=None,
        )
    )


def upload(
    client: TestClient,
    access_token: str,
    rom: Rom,
    device: Device,
    data: bytes,
    **params,
):
    return client.post(
        "/api/saves",
        params={
            "rom_id": rom.id,
            "slot": "autosave",
            "device_id": device.id,
            "emulator": "snes9x",
            **params,
        },
        files={"saveFile": ("game.srm", data)},
        headers=auth(access_token),
    )


async def test_an_adopted_upload_shows_its_screenshot_in_the_snapshot(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    pushed = await snapshot_push(admin_user, rom, game_file)
    synced_to(legacy_device, held_save(pushed))

    response = client.post(
        "/api/saves",
        params={
            "rom_id": rom.id,
            "slot": "autosave",
            "device_id": legacy_device.id,
            "emulator": "snes9x",
        },
        files={
            "saveFile": ("game.srm", LEGACY),
            "screenshotFile": ("game.png", b"png"),
        },
        headers=auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    current = channel_of(pushed).current_snapshot_id
    assert current is not None and current != pushed.snapshot.id
    body = client.get(f"/api/snapshots/{current}", headers=auth(access_token)).json()
    assert body["save"]["id"] == response.json()["id"]
    assert body["save"]["screenshot"] is not None
    assert body["thumbnail"] == body["save"]["screenshot"]


async def test_an_upload_named_like_a_held_save_leaves_its_bytes_alone(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
):
    pushed = await snapshot_push(admin_user, rom, game_file)
    held = held_save(pushed)

    response = client.post(
        "/api/saves",
        params={"rom_id": rom.id, "emulator": held.emulator},
        files={"saveFile": (held.file_name, b"overwritten")},
        headers=auth(access_token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert stored_bytes(held.full_path) == KEPT


async def test_a_state_upload_named_like_a_held_state_leaves_its_bytes_alone(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
):
    pushed = await snapshot_push(admin_user, rom, game_file)
    [state] = (
        db_snapshot_handler.get_stored_content(pushed.snapshot)
        .states["snes9x"]
        .values()
    )

    response = client.post(
        "/api/states",
        params={"rom_id": rom.id, "emulator": state.emulator},
        files={"stateFile": (state.file_name, b"overwritten")},
        headers=auth(access_token),
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert stored_bytes(state.full_path) == STATE


def synced_to(device: Device, save: Save) -> None:
    db_device_save_sync_handler.upsert_sync(
        device_id=device.id, save_id=save.id, synced_at=save.updated_at
    )


def channel_of(result: WriteResult) -> Channel:
    assert result.snapshot.channel_id is not None
    channel = db_snapshot_handler.get_channel(result.snapshot.channel_id)
    assert channel is not None
    return channel


def held_save(result: WriteResult) -> Save:
    save = db_save_handler.get_save(
        user_id=result.snapshot.user_id, id=result.snapshot.save_id or 0
    )
    assert save is not None
    return save


def negotiate(
    client: TestClient, access_token: str, device: Device, saves: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    response = client.post(
        "/api/sync/negotiate",
        json={"device_id": device.id, "saves": saves},
        headers=auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    operations: list[dict[str, Any]] = response.json()["operations"]
    return operations


def client_save(
    rom: Rom, data: bytes, updated_at: str = "2026-01-01T00:00:00Z"
) -> dict[str, Any]:
    return {
        "rom_id": rom.id,
        "file_name": "game.srm",
        "slot": "autosave",
        "content_hash": md5(data),
        "updated_at": updated_at,
        "file_size_bytes": len(data),
    }


async def test_a_legacy_device_downloads_what_a_snapshot_device_pushed(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    first = upload(client, access_token, rom, legacy_device, LEGACY)
    assert first.status_code == status.HTTP_200_OK
    channel_id = uuid.UUID(first.json()["channel_id"])
    pushed = await snapshot_push(admin_user, rom, game_file, channel_id=channel_id)

    [op] = negotiate(client, access_token, legacy_device, [client_save(rom, LEGACY)])

    assert op["action"] == "download"
    assert op["save_id"] == pushed.snapshot.save_id
    assert op["slot"] == "autosave"
    assert op["server_content_hash"] == md5(KEPT)


async def test_a_fresh_legacy_device_matches_a_channel_only_snapshots_wrote(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    pushed = await snapshot_push(admin_user, rom, game_file)

    [op] = negotiate(client, access_token, legacy_device, [client_save(rom, KEPT)])

    assert op["action"] == "no_op"
    assert op["save_id"] == pushed.snapshot.save_id


async def test_a_neutral_current_is_never_offered_to_a_legacy_device(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    await snapshot_push(admin_user, rom, game_file, fmt=SaveFormat.NEUTRAL)

    [op] = negotiate(client, access_token, legacy_device, [client_save(rom, LEGACY)])

    assert op["action"] == "upload"
    assert op["save_id"] is None


async def test_a_legacy_upload_becomes_the_current_and_keeps_the_states(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    pushed = await snapshot_push(admin_user, rom, game_file)
    synced_to(legacy_device, held_save(pushed))

    response = upload(client, access_token, rom, legacy_device, LEGACY)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    channel = channel_of(pushed)
    assert channel.current_snapshot_id is not None
    current = db_snapshot_handler.get_snapshot(channel.current_snapshot_id)
    assert current is not None
    assert current.save_id == body["id"]
    assert current.parent_snapshot_id == pushed.snapshot.id
    assert current.origin_device_id == legacy_device.id
    assert db_snapshot_handler.get_stored_content(current).resolved().bank == {
        "snes9x": {"auto": md5(STATE)}
    }
    assert body["slot"] == "autosave"
    assert body["content_hash"] == md5(LEGACY)


async def test_a_legacy_device_behind_the_snapshots_is_sent_back_to_negotiate(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    pushed = await snapshot_push(admin_user, rom, game_file)

    response = upload(client, access_token, rom, legacy_device, LEGACY)

    assert response.status_code == status.HTTP_409_CONFLICT
    assert channel_of(pushed).current_snapshot_id == pushed.snapshot.id


async def test_a_legacy_upload_leaves_a_hardcore_current_alone(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    pushed = await snapshot_push(admin_user, rom, game_file, is_hardcore=True)
    synced_to(legacy_device, held_save(pushed))

    response = upload(client, access_token, rom, legacy_device, LEGACY)

    assert response.status_code == status.HTTP_200_OK
    channel = channel_of(pushed)
    assert channel.current_snapshot_id == pushed.snapshot.id
    assert response.json()["channel_id"] == str(channel.id)


async def test_slot_cleanup_leaves_a_version_a_snapshot_holds(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    pushed = await snapshot_push(admin_user, rom, game_file)
    synced_to(legacy_device, held_save(pushed))
    first = upload(client, access_token, rom, legacy_device, LEGACY).json()
    adopted = db_save_handler.get_save(user_id=admin_user.id, id=first["id"])
    assert adopted is not None
    synced_to(legacy_device, adopted)

    second = upload(
        client,
        access_token,
        rom,
        legacy_device,
        b"another-legacy-upload",
        autocleanup=True,
        autocleanup_limit=1,
    )

    assert second.status_code == status.HTTP_200_OK
    assert db_save_handler.get_save(user_id=admin_user.id, id=first["id"]) is not None


async def test_a_legacy_device_without_the_save_downloads_it_under_its_slot(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    first = upload(client, access_token, rom, legacy_device, LEGACY)
    channel_id = uuid.UUID(first.json()["channel_id"])
    pushed = await snapshot_push(admin_user, rom, game_file, channel_id=channel_id)

    [op] = negotiate(client, access_token, legacy_device, [])

    assert op["action"] == "download"
    assert op["save_id"] == pushed.snapshot.save_id
    assert op["slot"] == "autosave"


async def test_a_legacy_upload_that_loses_a_race_is_kept_as_a_branch(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
    monkeypatch: pytest.MonkeyPatch,
):
    pushed = await snapshot_push(admin_user, rom, game_file)
    synced_to(legacy_device, held_save(pushed))
    racer = b"pushed-mid-upload"
    raced: list[WriteResult] = []

    async def push_first(write: SnapshotWrite) -> WriteResult:
        raced.append(
            await write_snapshot(
                push(
                    admin_user,
                    rom,
                    game_file,
                    Manifest(save=save_entry(racer, SaveFormat.NATIVE)),
                    expected=pushed.snapshot.id,
                    channel_id=pushed.snapshot.channel_id,
                    parts={SAVE_PART: part(racer)},
                )
            )
        )
        return await write_snapshot(write)

    monkeypatch.setattr(bridge, "write_snapshot", push_first)

    response = upload(client, access_token, rom, legacy_device, LEGACY)

    assert response.status_code == status.HTTP_200_OK
    [winner] = raced
    assert channel_of(pushed).current_snapshot_id == winner.snapshot.id
    [branch] = [
        s
        for s in db_snapshot_handler.get_channel_history(channel_of(pushed).id, 10)
        if s.save_id == response.json()["id"]
    ]
    assert branch.kind == SnapshotKind.BRANCH


async def test_a_zipped_legacy_upload_is_held_as_a_multi_file_save(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    pushed = await snapshot_push(admin_user, rom, game_file)
    synced_to(legacy_device, held_save(pushed))
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("card.mcd", LEGACY)
        zf.writestr("card.idx", b"index")

    response = upload(client, access_token, rom, legacy_device, buffer.getvalue())

    assert response.status_code == status.HTTP_200_OK
    held = db_save_handler.get_save(user_id=admin_user.id, id=response.json()["id"])
    assert held is not None
    assert held.shape == SaveShape.MULTI
    assert channel_of(pushed).current_snapshot_id != pushed.snapshot.id


@pytest.mark.parametrize(
    "emulators,offered", [(["mgba"], False), (["SNES9X"], True), (None, True)]
)
async def test_a_current_from_another_named_emulator_is_not_offered(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
    emulators: list[str] | None,
    offered: bool,
):
    pushed = await snapshot_push(admin_user, rom, game_file)
    response = client.post(
        "/api/sync/negotiate",
        json={
            "device_id": legacy_device.id,
            "saves": [client_save(rom, LEGACY)],
            "emulators": emulators,
        },
        headers=auth(access_token),
    )

    [op] = response.json()["operations"]
    assert (op["save_id"] == pushed.snapshot.save_id) is offered


async def test_a_legacy_upload_from_another_emulator_stays_off_the_snapshot_line(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    pushed = await snapshot_push(admin_user, rom, game_file)
    synced_to(legacy_device, held_save(pushed))

    response = upload(client, access_token, rom, legacy_device, LEGACY, emulator="mgba")

    assert response.status_code == status.HTTP_200_OK
    assert channel_of(pushed).current_snapshot_id == pushed.snapshot.id


@pytest.mark.parametrize("cores,offered", [(["snes9x"], True), (["bsnes"], False)])
async def test_a_named_core_decides_over_the_emulator_in_negotiate(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
    cores: list[str],
    offered: bool,
):
    pushed = await snapshot_push(
        admin_user, rom, game_file, emulator="argosy", core="snes9x"
    )
    response = client.post(
        "/api/sync/negotiate",
        json={
            "device_id": legacy_device.id,
            "saves": [client_save(rom, LEGACY)],
            "emulators": ["retroarch"],
            "cores": cores,
        },
        headers=auth(access_token),
    )

    [op] = response.json()["operations"]
    assert (op["save_id"] == pushed.snapshot.save_id) is offered


async def test_a_legacy_upload_on_the_same_core_joins_another_emulators_line(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    game_file: RomFile,
    legacy_device: Device,
):
    pushed = await snapshot_push(
        admin_user, rom, game_file, emulator="argosy", core="snes9x"
    )
    synced_to(legacy_device, held_save(pushed))

    response = upload(
        client,
        access_token,
        rom,
        legacy_device,
        LEGACY,
        emulator="retroarch",
        core="snes9x",
        core_version="1.62",
    )

    current = channel_of(pushed).current_snapshot_id
    assert current != pushed.snapshot.id
    held = db_save_handler.get_save(user_id=admin_user.id, id=response.json()["id"])
    assert held is not None
    assert (held.emulator, held.core, held.core_version) == (
        "retroarch",
        "snes9x",
        "1.62",
    )


async def test_a_legacy_reupload_keeps_the_versions_it_does_not_resend(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    def backup(data: bytes, **params: str):
        return client.post(
            "/api/saves",
            params={"rom_id": rom.id, "emulator": "retroarch", **params},
            files={"saveFile": ("backup.srm", data)},
            headers=auth(access_token),
        ).json()

    first = backup(b"first", emulator_version="1.21", core="mgba", core_version="0.10")
    second = backup(b"second")

    assert second["id"] == first["id"]
    saved = db_save_handler.get_save(user_id=admin_user.id, id=first["id"])
    assert saved is not None
    assert (saved.emulator_version, saved.core, saved.core_version) == (
        "1.21",
        "mgba",
        "0.10",
    )


async def test_a_legacy_state_upload_records_its_core(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    response = client.post(
        "/api/states",
        params={
            "rom_id": rom.id,
            "emulator": "retroarch",
            "emulator_version": "1.21",
            "core": "mgba",
            "core_version": "0.10",
        },
        files={"stateFile": ("game.state1", b"state")},
        headers=auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    state = db_state_handler.get_state(user_id=admin_user.id, id=response.json()["id"])
    assert state is not None
    assert (state.emulator_version, state.core, state.core_version) == (
        "1.21",
        "mgba",
        "0.10",
    )
    assert state.content_hash == md5(b"state")
