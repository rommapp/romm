import hashlib
import io
import json
import uuid
import zipfile
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests._zipfile_shim import reload_zipfile

from handler.database import db_device_handler, db_rom_handler, db_snapshot_handler
from handler.snapshots.manifest import Manifest, SaveEntry
from handler.snapshots.write import SAVE_PART, SnapshotWrite, UploadPart, write_snapshot
from models.assets import SaveFormat, SaveShape
from models.device import Device
from models.rom import Rom, RomFile
from models.user import User

SRAM = b"sram-bytes"
STATE = b"state-bytes"

pytestmark = pytest.mark.usefixtures("_isolated_assets_dir")


def md5(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


@pytest.fixture
def game_file(rom: Rom) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="game.sfc",
            file_path=rom.fs_path,
            file_size_bytes=1024,
            sha1_hash="b" * 40,
        )
    )


@pytest.fixture
def device(admin_user: User) -> Device:
    return db_device_handler.add_device(
        Device(id="odin", user_id=admin_user.id, name="Odin", client="argosy")
    )


def manifest(game_file: RomFile, **fields: Any) -> dict[str, Any]:
    return {"rom_file_id": game_file.id, "expected_current_id": None, **fields}


def save_entry(data: bytes = SRAM) -> dict[str, str]:
    return {"hash": md5(data), "shape": "SINGLE", "format": "neutral"}


def post(
    client: TestClient,
    headers: dict[str, str],
    body: dict[str, Any],
    files: dict[str, tuple[str, bytes]] | None = None,
    device_id: str | None = None,
):
    return client.post(
        "/api/snapshots",
        params={"device_id": device_id} if device_id else None,
        data={"manifest": json.dumps(body)},
        files=files or {"_": ("", b"")},
        headers=headers,
    )


def first_push(client, headers, game_file, device_id=None):
    response = post(
        client,
        headers,
        manifest(
            game_file,
            label="default",
            save=save_entry(),
            states={"snes9x": {"auto": md5(STATE)}},
            emulator="argosy",
        ),
        {
            "save": ("game.srm", SRAM),
            "state:snes9x:auto": ("game.state.auto", STATE),
            "state:snes9x:auto:screenshot": ("game.png", b"png"),
        },
        device_id=device_id,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()


def test_a_push_creates_the_channel_and_returns_the_snapshot(
    client: TestClient, headers: dict[str, str], game_file: RomFile, device: Device
):
    body = first_push(client, headers, game_file, device_id=device.id)

    assert body["digest"].startswith("sha256:")
    assert body["kind"] == "channel"
    assert body["channel"]["label"] == "default"
    assert body["channel"]["rom_file_id"] == game_file.id
    assert body["channel"]["current_snapshot_id"] == body["id"]
    assert body["device"] == {
        "id": "odin",
        "name": "Odin",
        "client": "argosy",
        "is_own": True,
    }
    assert [held["device"]["id"] for held in body["held_by"]] == ["odin"]
    assert body["save"]["content_hash"] == md5(SRAM)
    assert body["save"]["format"] == "neutral"
    state = body["states"]["snes9x"]["auto"]
    assert state["content_hash"] == md5(STATE)
    assert state["screenshot"] is not None


def test_the_saved_content_downloads(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    body = first_push(client, headers, game_file)

    response = client.get(body["save"]["download_path"], headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.content == SRAM


def test_a_push_without_needed_parts_lists_them(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    response = post(
        client,
        headers,
        manifest(
            game_file,
            label="default",
            save=save_entry(),
            states={"bsnes": {"3": md5(STATE)}},
        ),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"missing": ["save", "state:bsnes:3"]}


def test_pushing_current_again_returns_it_unchanged(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    body = first_push(client, headers, game_file)

    response = post(
        client,
        headers,
        manifest(
            game_file, channel_id=body["channel"]["id"], expected_current_id=body["id"]
        ),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == body["id"]


def test_a_stale_push_is_a_conflict_kept_as_a_branch(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    body = first_push(client, headers, game_file)
    channel_id = body["channel"]["id"]
    newer = b"newer"
    second = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=channel_id,
            expected_current_id=body["id"],
            save=save_entry(newer),
        ),
        {"save": ("game.srm", newer)},
    ).json()
    other = b"other"

    response = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=channel_id,
            expected_current_id=body["id"],
            save=save_entry(other),
        ),
        {"save": ("game.srm", other)},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    conflict = response.json()
    assert conflict["current"] == {"id": second["id"], "digest": second["digest"]}
    assert conflict["branch"]["kind"] == "branch"


def test_a_softcore_push_over_hardcore_asks_for_approval(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    hardcore = post(
        client,
        headers,
        manifest(game_file, label="default", save=save_entry(), is_hardcore=True),
        {"save": ("game.srm", SRAM)},
    ).json()
    softcore = b"softcore"

    response = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=hardcore["channel"]["id"],
            expected_current_id=hardcore["id"],
            save=save_entry(softcore),
        ),
        {"save": ("game.srm", softcore)},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"hardcore_downgrade": True}


def test_a_push_from_another_file_is_unprocessable(
    client: TestClient,
    headers: dict[str, str],
    game_file: RomFile,
    rom_file: RomFile,
):
    body = first_push(client, headers, game_file)

    response = post(
        client,
        headers,
        {
            "rom_file_id": rom_file.id,
            "channel_id": body["channel"]["id"],
            "expected_current_id": body["id"],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "rom_file_id" in response.json()["detail"]


def _neutral_unit(sram: bytes, clock: bytes) -> tuple[bytes, str]:
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("save.sram", sram)
        zf.writestr("clock.rtc", clock)
    archive = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        from handler.filesystem.assets_handler import hash_zip_contents

        return archive, hash_zip_contents(zf)


def test_a_clock_only_push_is_unchanged_and_progress_keeps_its_bytes(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    def push_unit(archive: bytes, content_hash: str, expected: int | None, **extra):
        return post(
            client,
            headers,
            manifest(
                game_file,
                label="default",
                expected_current_id=expected,
                save={"hash": content_hash, "shape": "MULTI", "format": "neutral"},
                **extra,
            ),
            {"save": ("save.zip", archive)},
        )

    first = push_unit(*_neutral_unit(SRAM, b"tick"), None).json()
    extra = {"channel_id": first["channel"]["id"]}
    clock_only = push_unit(*_neutral_unit(SRAM, b"tock"), first["id"], **extra)
    progress_archive, progress_hash = _neutral_unit(b"more", b"tock")
    progress = push_unit(progress_archive, progress_hash, first["id"], **extra)
    stored = client.get(progress.json()["save"]["download_path"], headers=headers)

    assert clock_only.status_code == status.HTTP_200_OK
    assert clock_only.json()["id"] == first["id"]
    assert progress.status_code == status.HTTP_201_CREATED
    assert stored.content == progress_archive


def test_a_neutral_save_with_foreign_member_names_is_unprocessable(
    client: TestClient,
    headers: dict[str, str],
    game_file: RomFile,
    rom: Rom,
    monkeypatch: pytest.MonkeyPatch,
):
    from handler.snapshots import neutral

    monkeypatch.setitem(
        neutral.NEUTRAL_FORMS, rom.platform_slug, neutral.NEUTRAL_FORMS["gb"]
    )
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("Pokemon Red.srm", SRAM)
        zf.writestr("clock.rtc", b"tick")

    response = post(
        client,
        headers,
        manifest(
            game_file,
            label="default",
            save={"hash": "0" * 32, "shape": "MULTI", "format": "neutral"},
        ),
        {"save": ("save.zip", buffer.getvalue())},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "Pokemon Red.srm" in response.json()["detail"]["save"]


def test_an_archive_escaping_its_folder_is_unprocessable(
    client: TestClient, headers: dict[str, str], game_file: RomFile, rom: Rom
):
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("../../escape.sav", SRAM)
    archive = buffer.getvalue()

    pushed = post(
        client,
        headers,
        manifest(
            game_file,
            label="default",
            save={"hash": "0" * 32, "shape": "MULTI", "format": "native"},
        ),
        {"save": ("save.zip", archive)},
    )
    uploaded = client.post(
        "/api/saves",
        params={"rom_id": rom.id},
        files={"saveFile": ("save.zip", archive)},
        headers=headers,
    )

    assert pushed.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "leaves the save folder" in pushed.json()["detail"]["save"]
    assert uploaded.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert (
        client.get("/api/saves", params={"rom_id": rom.id}, headers=headers).json()
        == []
    )


def test_a_save_whose_bytes_do_not_fit_its_shape_is_unprocessable(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("save.sram", SRAM)
    archive = buffer.getvalue()

    response = post(
        client,
        headers,
        manifest(
            game_file,
            label="default",
            save={"hash": md5(archive), "shape": "SINGLE", "format": "neutral"},
        ),
        {"save": ("save.zip", archive)},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_a_device_must_be_the_callers_own(
    client: TestClient,
    editor_headers: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    response = post(
        client,
        editor_headers,
        manifest(game_file, label="default", save=save_entry()),
        {"save": ("game.srm", SRAM)},
        device_id=device.id,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_the_current_listing_returns_each_channel_on_the_file(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    first = first_push(client, headers, game_file)
    second = post(
        client,
        headers,
        manifest(game_file, label="Speedrun", save=save_entry(b"run")),
        {"save": ("game.srm", b"run")},
    ).json()

    response = client.get(
        "/api/snapshots",
        params={"rom_file_id": game_file.id, "current": True},
        headers=headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert {item["id"] for item in response.json()} == {first["id"], second["id"]}


def test_history_lists_newest_first_and_pages(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    first = first_push(client, headers, game_file)
    channel_id = first["channel"]["id"]
    second = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=channel_id,
            expected_current_id=first["id"],
            save=save_entry(b"two"),
        ),
        {"save": ("game.srm", b"two")},
    ).json()

    page = client.get(
        "/api/snapshots", params={"channel_id": channel_id, "limit": 1}, headers=headers
    ).json()
    rest = client.get(
        "/api/snapshots",
        params={"channel_id": channel_id, "cursor": str(page[-1]["id"])},
        headers=headers,
    ).json()

    assert [item["id"] for item in page] == [second["id"]]
    assert [item["id"] for item in rest] == [first["id"]]


def test_another_user_sees_a_private_channel_as_missing(
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    game_file: RomFile,
):
    body = first_push(client, headers, game_file)

    snapshot = client.get(f"/api/snapshots/{body['id']}", headers=editor_headers)
    history = client.get(
        "/api/snapshots",
        params={"channel_id": body["channel"]["id"]},
        headers=editor_headers,
    )

    assert snapshot.status_code == status.HTTP_404_NOT_FOUND
    assert history.status_code == status.HTTP_404_NOT_FOUND


def test_a_public_channel_masks_the_owners_device_and_serves_its_content(
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    body = first_push(client, headers, game_file, device_id=device.id)
    shared = client.patch(
        f"/api/channels/{body['channel']['id']}",
        json={"is_public": True},
        headers=headers,
    )
    assert shared.status_code == status.HTTP_200_OK

    seen = client.get(f"/api/snapshots/{body['id']}", headers=editor_headers).json()
    content = client.get(seen["save"]["download_path"], headers=editor_headers)

    assert seen["device"] == {"id": None, "name": None, "client": None, "is_own": False}
    assert seen["held_by"] == []
    assert seen["channel"]["is_own"] is False
    assert content.status_code == status.HTTP_200_OK


def test_sharing_a_channel_serves_its_thumbnails_until_it_is_unshared(
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    body = first_push(client, headers, game_file, device_id=device.id)
    channel_url = f"/api/channels/{body['channel']['id']}"

    client.patch(channel_url, json={"is_public": True}, headers=headers)
    thumbnail = client.get(
        f"/api/snapshots/{body['id']}", headers=editor_headers
    ).json()["thumbnail"]
    shared = client.get(thumbnail["download_path"], headers=editor_headers)
    client.patch(channel_url, json={"is_public": False}, headers=headers)
    unshared = client.get(thumbnail["download_path"], headers=editor_headers)

    assert shared.status_code == status.HTTP_200_OK
    assert unshared.status_code == status.HTTP_404_NOT_FOUND


def test_a_screenshot_added_to_shared_content_is_served_to_others(
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    game_file: RomFile,
):
    body = first_push(client, headers, game_file)
    client.patch(
        f"/api/channels/{body['channel']['id']}",
        json={"is_public": True},
        headers=headers,
    )

    again = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=body["channel"]["id"],
            expected_current_id=body["id"],
            save=save_entry(),
        ),
        {"save_screenshot": ("game.png", b"png")},
    )
    screenshot = again.json()["save"]["screenshot"]
    shared = client.get(screenshot["download_path"], headers=editor_headers)

    assert again.status_code == status.HTTP_200_OK
    assert shared.status_code == status.HTTP_200_OK


def test_a_push_that_expects_nothing_of_a_channel_lands_as_a_branch(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    body = first_push(client, headers, game_file)
    other = b"other sram"

    response = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=body["channel"]["id"],
            save=save_entry(other),
        ),
        {"save": ("game.srm", other)},
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    branch = response.json()["branch"]
    assert branch["kind"] == "branch"
    assert branch["parent_snapshot_id"] is None
    assert branch["save"]["content_hash"] == md5(other)


@pytest.mark.parametrize("kind", ["saves", "states"])
def test_a_row_a_channel_holds_is_shared_with_the_channel(
    client: TestClient, headers: dict[str, str], game_file: RomFile, kind: str
):
    body = first_push(client, headers, game_file)
    row_id = (
        body["save"]["id"]
        if kind == "saves"
        else body["states"]["snes9x"]["auto"]["id"]
    )

    response = client.put(
        f"/api/{kind}/{row_id}/visibility", json={"is_public": True}, headers=headers
    )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_only_the_owner_renames_or_shares_a_channel(
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    game_file: RomFile,
):
    body = first_push(client, headers, game_file)
    path = f"/api/channels/{body['channel']['id']}"

    renamed = client.patch(path, json={"label": "Hard mode"}, headers=headers)
    foreign = client.patch(path, json={"label": "Mine now"}, headers=editor_headers)

    assert renamed.json()["label"] == "Hard mode"
    assert foreign.status_code == status.HTTP_404_NOT_FOUND


def test_deleting_a_channel_keeps_its_current_and_pins_as_backups(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    first = first_push(client, headers, game_file)
    channel_id = first["channel"]["id"]
    second = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=channel_id,
            expected_current_id=first["id"],
            save=save_entry(b"two"),
        ),
        {"save": ("game.srm", b"two")},
    ).json()
    third = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=channel_id,
            expected_current_id=second["id"],
            save=save_entry(b"three"),
        ),
        {"save": ("game.srm", b"three")},
    ).json()
    pinned = client.patch(
        f"/api/snapshots/{first['id']}", json={"is_pinned": True}, headers=headers
    )
    assert pinned.json()["is_pinned"] is True

    response = client.delete(f"/api/channels/{channel_id}", headers=headers)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert db_snapshot_handler.get_channel(uuid.UUID(channel_id)) is None
    for kept in (first, third):
        snapshot = db_snapshot_handler.get_snapshot(kept["id"])
        assert snapshot is not None and snapshot.kind == "archival"
    assert db_snapshot_handler.get_snapshot(second["id"]) is None


def test_a_channel_snapshot_cannot_be_shared_on_its_own(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    body = first_push(client, headers, game_file)

    response = client.patch(
        f"/api/snapshots/{body['id']}", json={"is_public": True}, headers=headers
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_a_managed_save_is_flagged_and_refuses_direct_changes(
    client: TestClient, headers: dict[str, str], game_file: RomFile, rom: Rom
):
    body = first_push(client, headers, game_file)
    save_id = body["save"]["id"]
    state_id = body["states"]["snes9x"]["auto"]["id"]

    listed = client.get("/api/saves", params={"rom_id": rom.id}, headers=headers).json()
    detail = client.get(f"/api/roms/{rom.id}", headers=headers).json()
    replaced = client.put(
        f"/api/saves/{save_id}",
        files={"saveFile": ("game.srm", b"tampered")},
        headers=headers,
    )
    deleted = client.post(
        "/api/saves/delete", json={"saves": [save_id]}, headers=headers
    )
    state_deleted = client.post(
        "/api/states/delete", json={"states": [state_id]}, headers=headers
    )
    renamed = client.put(
        f"/api/saves/{save_id}/file-name",
        json={"file_name": "renamed.srm"},
        headers=headers,
    )

    assert [save["channel_id"] for save in listed] == [body["channel"]["id"]]
    assert detail["all_user_saves"][0]["channel_id"] == body["channel"]["id"]
    assert detail["all_user_states"][0]["channel_id"] == body["channel"]["id"]
    assert replaced.status_code == status.HTTP_409_CONFLICT
    assert deleted.status_code == status.HTTP_409_CONFLICT
    assert state_deleted.status_code == status.HTTP_409_CONFLICT
    assert renamed.status_code == status.HTTP_200_OK


async def test_a_backup_is_replaced_and_deleted_with_its_archival_snapshot(
    client: TestClient, headers: dict[str, str], admin_user: User, rom: Rom
):
    archived = await write_snapshot(
        SnapshotWrite(
            author=admin_user,
            rom=rom,
            manifest=Manifest(
                save=SaveEntry(
                    hash=md5(SRAM), shape=SaveShape.SINGLE, format=SaveFormat.NATIVE
                )
            ),
            channel=None,
            parts={SAVE_PART: UploadPart(content=SRAM, file_name="backup.srm")},
        )
    )
    save_id = archived.snapshot.save_id
    listed = client.get("/api/saves", params={"rom_id": rom.id}, headers=headers).json()

    replaced = client.put(
        f"/api/saves/{save_id}",
        files={"saveFile": ("backup.srm", b"fixed")},
        headers=headers,
    )
    snapshot = db_snapshot_handler.get_snapshot(archived.snapshot.id)
    deleted = client.post(
        "/api/saves/delete", json={"saves": [save_id]}, headers=headers
    )

    assert listed[0]["channel_id"] is None
    assert replaced.status_code == status.HTTP_200_OK
    assert snapshot is not None and snapshot.digest != archived.snapshot.digest
    assert deleted.status_code == status.HTTP_200_OK
    assert db_snapshot_handler.get_snapshot(archived.snapshot.id) is None


def test_deleting_the_rom_detaches_its_channel_and_keeps_the_saves(
    client: TestClient, headers: dict[str, str], game_file: RomFile, rom: Rom
):
    body = first_push(client, headers, game_file)
    channel_id = body["channel"]["id"]

    db_rom_handler.delete_rom(rom.id)

    channel = db_snapshot_handler.get_channel(uuid.UUID(channel_id))
    history = client.get(
        "/api/snapshots", params={"channel_id": channel_id}, headers=headers
    )
    content = client.get(body["save"]["download_path"], headers=headers)
    legacy = client.get("/api/saves", headers=headers)
    assert channel is not None and channel.rom_id is None
    assert [item["id"] for item in history.json()] == [body["id"]]
    assert content.content == SRAM
    assert legacy.json() == []


def test_a_detached_channel_is_listed_and_attached_to_a_file_by_hand(
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    game_file: RomFile,
    rom: Rom,
):
    from tests.factories import make_platform, make_rom

    body = first_push(client, headers, game_file)
    channel_id = body["channel"]["id"]
    platform_id = rom.platform_id
    db_rom_handler.delete_rom(rom.id)
    readded = make_rom(rom.platform, "Game (Rev 1)")
    new_file = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=readded.id,
            file_name="game (rev 1).sfc",
            file_path=readded.fs_path,
            file_size_bytes=2048,
            sha1_hash="d" * 40,
        )
    )
    other_platform = make_rom(make_platform("other-platform"), "Other")
    other_file = db_rom_handler.add_rom_file(
        RomFile(
            rom_id=other_platform.id,
            file_name="other.bin",
            file_path=other_platform.fs_path,
            file_size_bytes=8,
        )
    )
    attach_url = f"/api/channels/{channel_id}/attach"

    listed = client.get(
        "/api/channels", params={"detached_platform_id": platform_id}, headers=headers
    ).json()
    elsewhere = client.post(
        attach_url, json={"rom_file_id": other_file.id}, headers=headers
    )
    not_theirs = client.post(
        attach_url, json={"rom_file_id": new_file.id}, headers=editor_headers
    )
    attached = client.post(
        attach_url, json={"rom_file_id": new_file.id}, headers=headers
    )
    again = client.post(attach_url, json={"rom_file_id": new_file.id}, headers=headers)
    detail = client.get(f"/api/roms/{readded.id}", headers=headers).json()
    saves = client.get(
        "/api/saves", params={"rom_id": readded.id}, headers=headers
    ).json()

    assert [channel["id"] for channel in listed] == [channel_id]
    assert [save["id"] for save in saves] == [body["save"]["id"]]
    assert elsewhere.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert not_theirs.status_code == status.HTTP_404_NOT_FOUND
    assert attached.status_code == status.HTTP_200_OK
    assert attached.json()["rom_file_id"] == new_file.id
    assert again.status_code == status.HTTP_409_CONFLICT
    assert [channel["id"] for channel in detail["user_channels"]] == [channel_id]
    assert detail["user_channels"][0]["current"]["id"] == body["id"]


def test_the_rom_names_the_file_its_channels_key_to(
    client: TestClient, headers: dict[str, str], rom: Rom
):
    added = {
        name: db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=name,
                file_path=rom.fs_path,
                file_size_bytes=8,
            )
        )
        for name in ("game (track 1).bin", "game.cue", "game (track 2).bin")
    }
    cue = added["game.cue"]

    detail = client.get(f"/api/roms/{rom.id}", headers=headers).json()

    assert detail["channel_file_id"] == cue.id


def test_a_device_reports_the_snapshot_it_applied(
    client: TestClient, headers: dict[str, str], game_file: RomFile, device: Device
):
    body = first_push(client, headers, game_file)

    response = client.put(
        f"/api/snapshots/{body['id']}/devices/{device.id}", headers=headers
    )
    seen = client.get(f"/api/snapshots/{body['id']}", headers=headers).json()

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert [held["device"]["id"] for held in seen["held_by"]] == [device.id]


def test_an_empty_channel_is_created_and_listed(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    client_id = str(uuid.uuid4())

    created = client.post(
        "/api/channels",
        json={"rom_file_id": game_file.id, "label": "New game", "id": client_id},
        headers=headers,
    )
    taken = client.post(
        "/api/channels",
        json={"rom_file_id": game_file.id, "label": "Again", "id": client_id},
        headers=headers,
    )
    listed = client.get(
        "/api/channels", params={"rom_file_id": game_file.id}, headers=headers
    ).json()
    snapshots = client.get(
        "/api/snapshots",
        params={"rom_file_id": game_file.id, "current": True},
        headers=headers,
    ).json()

    assert created.status_code == status.HTTP_201_CREATED
    assert created.json()["current"] is None
    assert created.json()["snapshot_count"] == 0
    assert taken.status_code == status.HTTP_409_CONFLICT
    assert [(c["id"], c["label"], c["current"]) for c in listed] == [
        (client_id, "New game", None)
    ]
    assert snapshots == []


def test_the_first_push_lands_in_a_precreated_channel(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    channel = client.post(
        "/api/channels",
        json={"rom_file_id": game_file.id, "label": "New game"},
        headers=headers,
    ).json()

    pushed = post(
        client,
        headers,
        manifest(game_file, channel_id=channel["id"], save=save_entry()),
        {"save": ("game.srm", SRAM)},
    )

    assert pushed.status_code == status.HTTP_201_CREATED
    assert pushed.json()["channel"]["label"] == "New game"


def test_the_rom_detail_lists_own_and_public_channels(
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    game_file: RomFile,
    rom: Rom,
):
    mine = first_push(client, headers, game_file)
    client.patch(
        f"/api/channels/{mine['channel']['id']}",
        json={"is_public": True},
        headers=headers,
    )
    theirs_private = post(
        client,
        editor_headers,
        manifest(game_file, label="Editor run", save=save_entry(b"x")),
        {"save": ("game.srm", b"x")},
    ).json()

    own_view = client.get(f"/api/roms/{rom.id}", headers=headers).json()
    editor_view = client.get(f"/api/roms/{rom.id}", headers=editor_headers).json()

    assert [c["id"] for c in own_view["user_channels"]] == [mine["channel"]["id"]]
    editor_channels = {c["id"]: c["is_own"] for c in editor_view["user_channels"]}
    assert editor_channels == {
        theirs_private["channel"]["id"]: True,
        mine["channel"]["id"]: False,
    }
    shared = next(c for c in editor_view["user_channels"] if not c["is_own"])
    assert shared["current"]["id"] == mine["id"]
    assert shared["owner_username"] == "test_admin"


def test_a_snapshot_falls_back_to_its_auto_state_screenshot(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    body = first_push(client, headers, game_file)

    assert body["save"]["screenshot"] is None
    assert body["thumbnail"] == body["states"]["snes9x"]["auto"]["screenshot"]
    assert body["thumbnail"] is not None


def _legacy_save_on_disk(
    rom: Rom,
    user: User,
    data: bytes,
    file_name: str = "Game [2026-01-01_00-00-00].srm",
    **fields: Any,
):
    from tests.factories import make_save

    from handler.filesystem import fs_asset_handler

    save = make_save(rom, user, file_name, **fields)
    path = fs_asset_handler.base_path / save.full_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return save


def test_a_backup_is_copied_into_a_channel_keeping_its_device(
    client: TestClient,
    headers: dict[str, str],
    game_file: RomFile,
    rom: Rom,
    admin_user: User,
    device: Device,
):
    legacy = _legacy_save_on_disk(
        rom, admin_user, b"legacy", origin_device_id=device.id
    )

    response = post(
        client,
        headers,
        manifest(game_file, label="default", save={"copy_of": legacy.id}),
    )

    body = response.json()
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert body["save"]["id"] != legacy.id
    assert body["save"]["content_hash"] == md5(b"legacy")
    assert body["save"]["format"] == "native"
    assert body["save"]["file_name"].startswith("Game [")
    assert body["device"]["id"] == device.id
    assert (
        client.get(f"/api/saves/{legacy.id}", headers=headers).json()["channel_id"]
        is None
    )


def test_a_copy_keeps_its_source_emulator_unless_the_push_names_one(
    client: TestClient,
    headers: dict[str, str],
    game_file: RomFile,
    rom: Rom,
    admin_user: User,
):
    legacy = _legacy_save_on_disk(
        rom,
        admin_user,
        b"legacy",
        emulator="retroarch",
        emulator_version="1.21",
        core="mgba",
        core_version="0.10.5",
    )
    other = _legacy_save_on_disk(
        rom,
        admin_user,
        b"other legacy",
        "Other [2026-01-01_00-00-00].srm",
        emulator="retroarch",
        core="mgba",
    )
    copied = post(
        client,
        headers,
        manifest(game_file, label="default", save={"copy_of": legacy.id}),
    ).json()["save"]
    renamed = post(
        client,
        headers,
        manifest(
            game_file,
            label="other",
            save={"copy_of": other.id},
            emulator="argosy",
        ),
    ).json()["save"]

    assert (
        copied["emulator"],
        copied["emulator_version"],
        copied["core"],
        copied["core_version"],
    ) == ("retroarch", "1.21", "mgba", "0.10.5")
    assert (renamed["emulator"], renamed["core"]) == ("argosy", None)


def test_a_push_records_its_core_on_the_save_and_that_cores_states(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    body = post(
        client,
        headers,
        manifest(
            game_file,
            label="default",
            save=save_entry(),
            states={
                "snes9x": {"auto": md5(STATE)},
                "bsnes": {"auto": md5(b"other-core")},
            },
            emulator="retroarch",
            emulator_version="1.21",
            core="SNES9X",
            core_version="1.62",
        ),
        {
            "save": ("game.srm", SRAM),
            "state:snes9x:auto": ("game.state", STATE),
            "state:bsnes:auto": ("game.state", b"other-core"),
        },
    ).json()

    assert (body["save"]["core"], body["save"]["core_version"]) == ("SNES9X", "1.62")
    assert body["save"]["emulator_version"] == "1.21"
    assert body["states"]["snes9x"]["auto"]["core_version"] == "1.62"
    assert body["states"]["bsnes"]["auto"]["core_version"] is None


def test_a_copy_with_no_device_belongs_to_the_web_ui(
    client: TestClient,
    headers: dict[str, str],
    game_file: RomFile,
    rom: Rom,
    admin_user: User,
):
    legacy = _legacy_save_on_disk(rom, admin_user, b"browser upload")

    body = post(
        client,
        headers,
        manifest(game_file, label="default", save={"copy_of": legacy.id}),
    ).json()

    assert body["device"]["client"] == "web"
    assert body["device"]["is_own"] is True


def test_restoring_from_the_web_keeps_the_source_device(
    client: TestClient, headers: dict[str, str], game_file: RomFile, device: Device
):
    first = first_push(client, headers, game_file, device_id=device.id)
    channel_id = first["channel"]["id"]
    second = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=channel_id,
            expected_current_id=first["id"],
            save=save_entry(b"later"),
        ),
        {"save": ("game.srm", b"later")},
    ).json()

    restored = post(
        client,
        headers,
        manifest(
            game_file,
            channel_id=channel_id,
            expected_current_id=second["id"],
            parent_snapshot_id=first["id"],
            save=save_entry(),
            states={"snes9x": {"auto": md5(STATE)}},
        ),
    ).json()

    assert restored["parent_snapshot_id"] == first["id"]
    assert restored["device"]["id"] == device.id
    assert restored["held_by"] == []


def test_a_save_names_exactly_one_source(
    client: TestClient, headers: dict[str, str], game_file: RomFile
):
    response = post(
        client,
        headers,
        manifest(
            game_file,
            label="default",
            save={
                "copy_of": 1,
                "hash": md5(SRAM),
                "shape": "SINGLE",
                "format": "native",
            },
        ),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
