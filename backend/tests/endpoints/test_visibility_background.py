"""Hidden ROMs and platforms stay out of sync, installs, recommendations, playlists,
the setup wizard and the feeds."""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.endpoints.test_music import (  # noqa: F401
    _track_id,
    music_library,
)
from tests.endpoints.test_permissions_visibility import _auth, _hide
from tests.factories import make_device_token, make_platform, make_rom, make_save
from tests.handler.recommendation.test_builder import make_rom as make_rated_rom

from endpoints.device import install as device_install
from handler.database import db_device_handler, db_rom_handler
from handler.device_install import device_install_handler
from handler.recommendation import SimilarityBuilder, invalidate_cached_feed
from models.device import Device
from models.permission import PermEntity
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User


def _negotiate(
    client: TestClient, user: User, device_id: str, saves: list[dict[str, Any]]
) -> dict[str, Any]:
    response = client.post(
        "/api/sync/negotiate",
        json={"device_id": device_id, "saves": saves},
        headers=_auth(user),
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    body: dict[str, Any] = response.json()
    return body


class TestSyncNegotiate:
    def test_a_hidden_roms_save_is_neither_offered_nor_paired(
        self, client, viewer_user: User, rom: Rom, second_rom: Rom
    ):
        device = db_device_handler.add_device(
            Device(id="vis-neg", user_id=viewer_user.id, sync_enabled=True)
        )
        hidden = make_save(
            rom, viewer_user, "hidden.sav", slot="autosave", content_hash="h1"
        )
        shown = make_save(
            second_rom, viewer_user, "shown.sav", slot="autosave", content_hash="s1"
        )
        _hide(PermEntity.ROMS, rom.id, viewer_user.id)

        offered = _negotiate(client, viewer_user, device.id, [])
        assert [op["save_id"] for op in offered["operations"]] == [shown.id]

        client_save = {
            "rom_id": rom.id,
            "file_name": hidden.file_name,
            "slot": "autosave",
            "content_hash": "changed",
            "updated_at": "2099-01-01T00:00:00Z",
            "file_size_bytes": 1,
        }
        with mock.patch(
            "endpoints.sync.emit_sync_conflict", new_callable=AsyncMock
        ) as emit:
            paired = _negotiate(client, viewer_user, device.id, [client_save])

        [op] = [o for o in paired["operations"] if o["rom_id"] == rom.id]
        assert (op["action"], op["save_id"]) == ("upload", None)
        emit.assert_not_awaited()


def _add_game_file(rom: Rom) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name=f"{rom.fs_name}.bin",
            file_path=rom.fs_path,
            file_size_bytes=1,
            category=RomFileCategory.GAME,
        )
    )


class TestDeviceInstalls:
    @pytest.fixture(autouse=True)
    def emits(self, mocker) -> dict[str, AsyncMock]:
        return {
            name: mocker.patch.object(device_install, name, AsyncMock())
            for name in ("emit_install_queued", "emit_install_updated", "notify")
        }

    @pytest.fixture
    def device(self, editor_user: User) -> Device:
        return db_device_handler.add_device(
            Device(
                id="vis-install",
                user_id=editor_user.id,
                capabilities={"remote_install": True},
            )
        )

    @pytest.fixture
    def device_headers(self, editor_user: User, device: Device) -> dict[str, str]:
        _, raw_token = make_device_token(editor_user, device.id)
        return {"Authorization": f"Bearer {raw_token}"}

    def _queue(self, client, editor_user: User, rom: Rom) -> str:
        _add_game_file(rom)
        response = client.post(
            "/api/devices/vis-install/installs",
            json={"rom_id": rom.id},
            headers=_auth(editor_user),
        )
        assert response.status_code == status.HTTP_201_CREATED, response.text
        return str(response.json()["id"])

    def test_a_request_for_a_rom_hidden_later_is_left_out(
        self, client, editor_user, device, device_headers, rom, second_rom
    ):
        hidden_id = self._queue(client, editor_user, rom)
        shown_id = self._queue(client, editor_user, second_rom)
        _hide(PermEntity.ROMS, rom.id, editor_user.id)

        listed = client.get("/api/devices/vis-install/installs", headers=device_headers)
        claimed = client.post(
            "/api/devices/vis-install/installs/claim", headers=device_headers
        )

        assert [r["id"] for r in listed.json()] == [shown_id]
        assert [r["id"] for r in claimed.json()] == [shown_id]
        stored = asyncio.run(device_install_handler.get(hidden_id))
        assert stored is not None and stored.status == "pending"

    def test_the_outcome_of_a_rom_hidden_meanwhile_does_not_name_it(
        self, client, editor_user, device, device_headers, rom, emits
    ):
        request_id = self._queue(client, editor_user, rom)
        client.post("/api/devices/vis-install/installs/claim", headers=device_headers)
        _hide(PermEntity.ROMS, rom.id, editor_user.id)

        response = client.put(
            f"/api/devices/vis-install/installs/{request_id}",
            json={"status": "done"},
            headers=device_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        _, _, _, data = emits["notify"].await_args.args
        assert (data["rom_id"], data["rom_name"]) == (None, None)


def test_a_hidden_seed_is_not_named(client, viewer_user: User, platform: Platform):
    seed = make_rated_rom(
        platform,
        "Super Metroid",
        igdb_id=5001,
        genres=["Platform"],
        franchises=["Metroid"],
    )
    make_rated_rom(
        platform,
        "Metroid Fusion",
        igdb_id=5002,
        genres=["Platform"],
        franchises=["Metroid"],
    )
    SimilarityBuilder().build()
    rom_user = db_rom_handler.add_rom_user(seed.id, viewer_user.id)
    db_rom_handler.update_rom_user(
        rom_user.id, {"rating": 10, "last_played": datetime.now(timezone.utc)}
    )
    invalidate_cached_feed(viewer_user.id)
    _hide(PermEntity.ROMS, seed.id, viewer_user.id)

    body = client.get("/api/recommendations", headers=_auth(viewer_user)).json()

    assert body
    assert all(
        (entry["seed_rom_id"], entry["seed_rom_name"]) == (None, None) for entry in body
    )


def test_a_playlists_track_count_leaves_out_hidden_tracks(
    client,
    access_token: str,
    editor_user: User,
    music_library,  # noqa: F811
):
    admin = {"Authorization": f"Bearer {access_token}"}
    playlist_id = client.post(
        "/api/music/playlists", json={"name": "Mix", "is_public": True}, headers=admin
    ).json()["id"]
    client.post(
        f"/api/music/playlists/{playlist_id}/tracks",
        json={
            "rom_file_ids": [
                _track_id(client, access_token, title)
                for title in ("Green Hill", "Overworld")
            ]
        },
        headers=admin,
    )
    _hide(PermEntity.PLATFORMS, music_library["platform_b"].id, editor_user.id)

    listed = client.get("/api/music/playlists", headers=_auth(editor_user)).json()
    detail = client.get(
        f"/api/music/playlists/{playlist_id}", headers=_auth(editor_user)
    ).json()

    assert [p["track_count"] for p in listed] == [1]
    assert detail["track_count"] == 1


def test_setup_library_lists_a_hidden_platform_as_unknown(
    client, viewer_user: User, rom: Rom
):
    hidden = make_platform("snes")
    _hide(PermEntity.PLATFORMS, hidden.id, viewer_user.id)

    response = client.get("/api/setup/library", headers=_auth(viewer_user))

    assert response.status_code == status.HTTP_200_OK
    supported = {p["slug"]: p for p in response.json()["supported_platforms"]}
    assert supported["snes"]["id"] == -1


class TestFeeds:
    def test_a_hidden_platform_reads_as_missing(self, client, viewer_user: User):
        missing = client.get("/api/feeds/kekatsu/nds", headers=_auth(viewer_user))
        _hide(PermEntity.PLATFORMS, make_platform("nds").id, viewer_user.id)
        hidden = client.get("/api/feeds/kekatsu/nds", headers=_auth(viewer_user))

        assert hidden.status_code == status.HTTP_404_NOT_FOUND
        assert hidden.json() == missing.json()

    def test_a_visible_platform_sharing_a_hidden_ones_slug_is_served(
        self, client, viewer_user: User
    ):
        hidden = make_platform("nds")
        make_platform("nds", fs_slug="nintendo-ds")
        _hide(PermEntity.PLATFORMS, hidden.id, viewer_user.id)

        response = client.get("/api/feeds/kekatsu/nds", headers=_auth(viewer_user))

        assert response.status_code == status.HTTP_200_OK

    def test_tinfoil_reports_a_hidden_switch_as_missing(
        self, client, viewer_user: User
    ):
        switch = make_platform("switch")
        make_rom(switch, "Zelda", fs_extension="nsp")
        _hide(PermEntity.PLATFORMS, switch.id, viewer_user.id)

        body = client.get(
            "/api/feeds/tinfoil?slug=switch", headers=_auth(viewer_user)
        ).json()

        assert body["error"] == "Nintendo Switch platform not found"
        assert body["files"] == []
