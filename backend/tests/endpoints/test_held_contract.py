"""The held, latest known and pinned contract, over HTTP with a device-bound token."""

import json
import uuid
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx2 import Response
from tests.factories import make_device_token
from tests.handler.snapshots.pushes import md5

from handler.database import db_device_handler, db_rom_handler, db_snapshot_handler
from handler.snapshots import retention
from models.device import Device
from models.device_channel_sync import DeviceChannelSync
from models.rom import Rom, RomFile
from models.user import User

pytestmark = pytest.mark.usefixtures("_isolated_assets_dir")

DEVICE_SCOPES = "roms.read assets.read assets.write"


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


@pytest.fixture
def bound(admin_user: User, device: Device) -> dict[str, str]:
    _, raw = make_device_token(admin_user, device.id, scopes=DEVICE_SCOPES)
    return {"Authorization": f"Bearer {raw}"}


def push(
    client: TestClient,
    headers: dict[str, str],
    game_file: RomFile,
    data: bytes,
    **fields: Any,
) -> Response:
    """A save push that leaves `expected_current_id` out unless `fields` names it."""
    body = {
        "rom_file_id": game_file.id,
        "save": {"hash": md5(data), "shape": "SINGLE", "format": "neutral"},
        **fields,
    }
    return client.post(
        "/api/snapshots",
        data={"manifest": json.dumps(body)},
        files={"save": ("game.srm", data)},
        headers=headers,
    )


Snapshot = dict[str, Any]


def start(client: TestClient, headers: dict[str, str], game_file: RomFile) -> Snapshot:
    response = push(
        client,
        headers,
        game_file,
        b"start",
        label="default",
        expected_current_id=None,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    body: Snapshot = response.json()
    return body


def follow(
    client: TestClient,
    headers: dict[str, str],
    game_file: RomFile,
    after: Snapshot,
    data: bytes,
) -> Snapshot:
    """A push from the web, with no device, on top of `after`."""
    response = push(
        client,
        headers,
        game_file,
        data,
        channel_id=after["channel"]["id"],
        expected_current_id=after["id"],
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    body: Snapshot = response.json()
    return body


def chain(
    client: TestClient, headers: dict[str, str], game_file: RomFile, length: int
) -> list[Snapshot]:
    pushed = [start(client, headers, game_file)]
    for step in range(1, length):
        pushed.append(
            follow(client, headers, game_file, pushed[-1], f"step-{step}".encode())
        )
    return pushed


def hold(client: TestClient, headers: dict[str, str], id: int) -> Response:
    return client.get(f"/api/snapshots/{id}", params={"hold": True}, headers=headers)


def held_by(client: TestClient, headers: dict[str, str], id: int) -> list[str]:
    response = client.get(f"/api/snapshots/{id}", headers=headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    return [held["device"]["id"] for held in response.json()["held_by"]]


def sync(device_id: str, channel_id: str) -> DeviceChannelSync | None:
    return db_snapshot_handler.get_device_sync(device_id, uuid.UUID(channel_id))


def assert_conflict(response: Response, current_id: int, reason: str) -> Snapshot:
    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    body: Snapshot = response.json()
    assert set(body) >= {"current", "branch", "reason"}
    assert body["current"]["id"] == current_id
    assert body["current"]["digest"]
    assert body["branch"]["kind"] == "branch"
    assert body["branch"]["channel"]["current_snapshot_id"] == current_id
    assert body["reason"] == reason
    return body


# Held


def test_a_push_holds_the_current_it_created(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first = start(client, bound, game_file)
    second = push(
        client, bound, game_file, b"next", channel_id=first["channel"]["id"]
    ).json()

    assert second["kind"] == "channel"
    assert held_by(client, headers, first["id"]) == []
    assert held_by(client, headers, second["id"]) == [device.id]


def test_a_push_that_branches_holds_the_branch(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first = start(client, bound, game_file)
    follow(client, headers, game_file, first, b"elsewhere")

    response = push(
        client, bound, game_file, b"mine", channel_id=first["channel"]["id"]
    )
    branch = response.json()["branch"]

    assert held_by(client, headers, branch["id"]) == [device.id]
    assert held_by(client, headers, first["id"]) == []


def test_a_plain_fetch_holds_nothing(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first, second = chain(client, headers, game_file, 2)

    for snapshot in (first, second):
        assert client.get(f"/api/snapshots/{snapshot['id']}", headers=bound).is_success

    assert sync(device.id, first["channel"]["id"]) is None
    assert held_by(client, headers, first["id"]) == []
    assert held_by(client, headers, second["id"]) == []


def test_a_download_with_hold_holds_it(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first, _ = chain(client, headers, game_file, 2)

    response = hold(client, bound, first["id"])

    assert response.status_code == status.HTTP_200_OK
    assert [h["device"]["id"] for h in response.json()["held_by"]] == [device.id]


def test_holding_another_snapshot_replaces_it(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first, second = chain(client, headers, game_file, 2)
    hold(client, bound, first["id"])

    hold(client, bound, second["id"])

    assert held_by(client, headers, first["id"]) == []
    assert held_by(client, headers, second["id"]) == [device.id]


def test_clearing_held_leaves_the_device_holding_nothing(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first = start(client, bound, game_file)

    response = client.delete(
        f"/api/channels/{first['channel']['id']}/held", headers=bound
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert held_by(client, headers, first["id"]) == []
    assert sync(device.id, first["channel"]["id"]) is None


def test_a_read_only_token_can_hold_and_clear(
    client: TestClient,
    headers: dict[str, str],
    admin_user: User,
    game_file: RomFile,
    device: Device,
):
    first = start(client, headers, game_file)
    _, raw = make_device_token(admin_user, device.id, scopes="roms.read assets.read")
    read_only = {"Authorization": f"Bearer {raw}"}

    held = hold(client, read_only, first["id"])
    cleared = client.delete(
        f"/api/channels/{first['channel']['id']}/held", headers=read_only
    )

    assert held.status_code == status.HTTP_200_OK
    assert cleared.status_code == status.HTTP_204_NO_CONTENT
    assert sync(device.id, first["channel"]["id"]) is None


def test_held_by_lists_only_the_viewers_devices(
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    bound: dict[str, str],
    editor_user: User,
    game_file: RomFile,
    device: Device,
):
    first = start(client, bound, game_file)
    client.patch(
        f"/api/channels/{first['channel']['id']}",
        json={"is_public": True},
        headers=headers,
    )
    editor_device = db_device_handler.add_device(
        Device(id="editor-handheld", user_id=editor_user.id, name="Handheld")
    )
    _, raw = make_device_token(editor_user, editor_device.id, scopes=DEVICE_SCOPES)
    hold(client, {"Authorization": f"Bearer {raw}"}, first["id"])

    assert held_by(client, headers, first["id"]) == [device.id]
    assert held_by(client, editor_headers, first["id"]) == [editor_device.id]


# Latest known


@pytest.mark.parametrize("listing", ["channels", "current", "history"])
def test_listing_records_the_latest_known_and_keeps_what_is_held(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
    listing: str,
):
    first = start(client, bound, game_file)
    channel_id = first["channel"]["id"]
    second = follow(client, headers, game_file, first, b"elsewhere")
    path, params = {
        "channels": ("/api/channels", {"rom_file_id": game_file.id}),
        "current": ("/api/snapshots", {"rom_file_id": game_file.id, "current": True}),
        "history": ("/api/snapshots", {"channel_id": channel_id}),
    }[listing]

    response = client.get(path, params=params, headers=bound)
    recorded = sync(device.id, channel_id)

    assert response.status_code == status.HTTP_200_OK
    assert recorded is not None
    assert recorded.latest_known_id == second["id"]
    assert recorded.base_snapshot_id == first["id"]
    assert held_by(client, headers, first["id"]) == [device.id]


def test_a_history_page_past_the_newest_records_nothing(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    _, second, third = chain(client, headers, game_file, 3)

    client.get(
        "/api/snapshots",
        params={"channel_id": third["channel"]["id"], "cursor": str(second["id"])},
        headers=bound,
    )

    assert sync(device.id, third["channel"]["id"]) is None


def test_a_branching_push_records_the_current_it_missed(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first = start(client, bound, game_file)
    second = follow(client, headers, game_file, first, b"elsewhere")

    push(client, bound, game_file, b"mine", channel_id=first["channel"]["id"])
    recorded = sync(device.id, first["channel"]["id"])

    assert recorded is not None
    assert recorded.latest_known_id == second["id"]


def test_holding_an_older_snapshot_records_the_current_as_latest_known(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first, second = chain(client, headers, game_file, 2)

    hold(client, bound, first["id"])
    recorded = sync(device.id, first["channel"]["id"])

    assert recorded is not None
    assert recorded.latest_known_id == second["id"]


def test_a_push_after_holding_an_older_snapshot_becomes_the_current(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
):
    first, second = chain(client, headers, game_file, 2)
    hold(client, bound, first["id"])

    response = push(
        client, bound, game_file, b"older", channel_id=first["channel"]["id"]
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["parent_snapshot_id"] == first["id"]


def test_listing_never_changes_what_is_held(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first, second = chain(client, headers, game_file, 2)
    hold(client, bound, first["id"])
    before = sync(device.id, first["channel"]["id"])

    client.get("/api/channels", params={"rom_file_id": game_file.id}, headers=bound)
    client.get(
        "/api/snapshots",
        params={"rom_file_id": game_file.id, "current": True},
        headers=bound,
    )
    after = sync(device.id, first["channel"]["id"])

    assert before is not None and after is not None
    assert after.base_snapshot_id == first["id"]
    assert after.synced_at == before.synced_at
    assert held_by(client, headers, second["id"]) == []


# The push table


def test_known_same_held_same_becomes_the_current(
    client: TestClient,
    bound: dict[str, str],
    game_file: RomFile,
):
    first = start(client, bound, game_file)

    response = push(
        client, bound, game_file, b"next", channel_id=first["channel"]["id"]
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    body = response.json()
    assert body["kind"] == "channel"
    assert body["parent_snapshot_id"] == first["id"]
    assert body["channel"]["current_snapshot_id"] == body["id"]


def test_known_same_held_older_becomes_the_current_keeping_the_replaced(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
):
    first, second = chain(client, headers, game_file, 2)
    channel_id = first["channel"]["id"]
    client.get("/api/snapshots", params={"channel_id": channel_id}, headers=bound)
    hold(client, bound, first["id"])

    response = push(client, bound, game_file, b"older", channel_id=channel_id)

    assert response.status_code == status.HTTP_201_CREATED, response.text
    body = response.json()
    assert body["parent_snapshot_id"] == first["id"]
    assert body["channel"]["current_snapshot_id"] == body["id"]
    history = client.get(
        "/api/snapshots", params={"channel_id": channel_id}, headers=headers
    ).json()
    assert second["id"] in [snapshot["id"] for snapshot in history]


def test_known_different_held_same_is_a_moved_branch(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
):
    first = start(client, bound, game_file)
    second = follow(client, headers, game_file, first, b"elsewhere")

    response = push(
        client, bound, game_file, b"mine", channel_id=first["channel"]["id"]
    )

    body = assert_conflict(response, second["id"], "moved")
    assert body["branch"]["parent_snapshot_id"] == first["id"]


def test_known_different_held_older_is_a_moved_from_older_branch(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
):
    first, second = chain(client, headers, game_file, 2)
    channel_id = first["channel"]["id"]
    client.get("/api/snapshots", params={"channel_id": channel_id}, headers=bound)
    hold(client, bound, first["id"])
    third = follow(client, headers, game_file, second, b"elsewhere")

    response = push(client, bound, game_file, b"older", channel_id=channel_id)

    body = assert_conflict(response, third["id"], "moved_from_older")
    assert body["branch"]["parent_snapshot_id"] == first["id"]


def test_with_no_sync_record_a_parent_on_the_current_becomes_the_current(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    _, second = chain(client, headers, game_file, 2)
    assert sync(device.id, second["channel"]["id"]) is None

    response = push(
        client,
        bound,
        game_file,
        b"next",
        channel_id=second["channel"]["id"],
        parent_snapshot_id=second["id"],
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["channel"]["current_snapshot_id"] == response.json()["id"]


@pytest.mark.parametrize("parent", ["older", "none"])
def test_with_no_sync_record_any_other_parent_lands_as_a_branch(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    parent: str,
):
    first, second = chain(client, headers, game_file, 2)
    fields = {"parent_snapshot_id": first["id"]} if parent == "older" else {}

    response = push(
        client, bound, game_file, b"next", channel_id=first["channel"]["id"], **fields
    )

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    assert response.json()["current"]["id"] == second["id"]
    assert response.json()["branch"]["parent_snapshot_id"] == (
        first["id"] if parent == "older" else None
    )


def test_an_explicit_stale_expected_overrides_a_device_on_the_current(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
):
    first, second = chain(client, headers, game_file, 2)
    hold(client, bound, second["id"])

    response = push(
        client,
        bound,
        game_file,
        b"mine",
        channel_id=first["channel"]["id"],
        expected_current_id=first["id"],
    )

    assert response.status_code == status.HTTP_409_CONFLICT, response.text
    assert response.json()["current"]["id"] == second["id"]


def test_an_explicit_current_expected_overrides_a_device_that_missed_a_push(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
):
    first = start(client, bound, game_file)
    second = follow(client, headers, game_file, first, b"elsewhere")

    response = push(
        client,
        bound,
        game_file,
        b"mine",
        channel_id=first["channel"]["id"],
        expected_current_id=second["id"],
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert response.json()["parent_snapshot_id"] == second["id"]


# Retention and pins


@pytest.fixture
def small_retention(monkeypatch):
    monkeypatch.setattr(retention, "SNAPSHOT_RETENTION", 2)


def exists(id: int) -> bool:
    return db_snapshot_handler.get_snapshot(id) is not None


@pytest.mark.usefixtures("small_retention")
def test_retention_prunes_a_held_unpinned_snapshot_and_the_device_holds_nothing(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first = start(client, bound, game_file)
    channel_id = first["channel"]["id"]
    second = follow(client, headers, game_file, first, b"two")
    third = follow(client, headers, game_file, second, b"three")

    recorded = sync(device.id, channel_id)
    for kept in (second, third):
        assert held_by(client, headers, kept["id"]) == []
    branched = push(client, bound, game_file, b"mine", channel_id=channel_id)

    assert not exists(first["id"])
    assert recorded is not None
    assert recorded.base_snapshot_id is None
    assert branched.status_code == status.HTTP_409_CONFLICT, branched.text
    assert branched.json()["branch"]["parent_snapshot_id"] is None


@pytest.mark.usefixtures("small_retention")
def test_after_a_prune_a_parent_on_the_current_becomes_the_current(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
):
    first = start(client, bound, game_file)
    second = follow(client, headers, game_file, first, b"two")
    third = follow(client, headers, game_file, second, b"three")

    response = push(
        client,
        bound,
        game_file,
        b"mine",
        channel_id=first["channel"]["id"],
        parent_snapshot_id=third["id"],
    )

    assert not exists(first["id"])
    assert response.status_code == status.HTTP_201_CREATED, response.text


@pytest.mark.usefixtures("small_retention")
def test_a_held_snapshot_the_owner_pinned_survives_retention(
    client: TestClient,
    headers: dict[str, str],
    bound: dict[str, str],
    game_file: RomFile,
    device: Device,
):
    first = start(client, bound, game_file)
    client.patch(
        f"/api/snapshots/{first['id']}", json={"is_pinned": True}, headers=headers
    )
    latest = first
    for step in range(4):
        latest = follow(client, headers, game_file, latest, f"s{step}".encode())

    assert exists(first["id"])
    assert held_by(client, headers, first["id"]) == [device.id]


@pytest.mark.usefixtures("small_retention")
def test_another_readers_pin_keeps_a_snapshot_until_unsharing_drops_it(
    client: TestClient,
    headers: dict[str, str],
    editor_headers: dict[str, str],
    game_file: RomFile,
):
    first = start(client, headers, game_file)
    channel_path = f"/api/channels/{first['channel']['id']}"
    client.patch(channel_path, json={"is_public": True}, headers=headers)
    pinned = client.patch(
        f"/api/snapshots/{first['id']}",
        json={"is_pinned": True},
        headers=editor_headers,
    ).json()
    owners_view = client.get(f"/api/snapshots/{first['id']}", headers=headers).json()
    latest = first
    for step in range(3):
        latest = follow(client, headers, game_file, latest, f"s{step}".encode())
    survived = exists(first["id"])

    client.patch(channel_path, json={"is_public": False}, headers=headers)
    follow(client, headers, game_file, latest, b"after-unshare")

    assert (pinned["is_pinned"], owners_view["is_pinned"]) == (True, False)
    assert survived
    assert not exists(first["id"])
