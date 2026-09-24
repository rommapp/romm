from fastapi import status
from fastapi.testclient import TestClient
from tests.audit_events import recorded_events

from handler.database import (
    db_audit_event_handler,
    db_collection_handler,
    db_rom_handler,
)
from models.collection import Collection
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestRomContent:
    def test_a_download_is_recorded_once(
        self, client: TestClient, access_token: str, rom: Rom, rom_file: RomFile
    ):
        for _ in range(2):
            response = client.get(
                f"/api/roms/{rom.id}/content/test_rom.zip",
                headers=_auth(access_token),
                follow_redirects=False,
            )
            assert response.status_code == status.HTTP_200_OK

        [event] = recorded_events()
        assert event.action == "rom.download"
        assert event.actor_name == "test_admin"
        assert (event.target_type, event.target_id) == ("rom", str(rom.id))
        assert event.data["file_name"] == "test_rom.zip"

    def test_a_players_fetch_is_a_player_load(
        self, client: TestClient, access_token: str, rom: Rom, rom_file: RomFile
    ):
        for purpose in ("play", "download"):
            response = client.get(
                f"/api/roms/{rom.id}/content/test_rom.zip",
                params={"purpose": purpose},
                headers=_auth(access_token),
                follow_redirects=False,
            )
            assert response.status_code == status.HTTP_200_OK

        assert sorted(event.action for event in recorded_events()) == [
            "rom.download",
            "rom.player_load",
        ]

    def test_a_resumed_transfer_is_not_a_new_download(
        self, client: TestClient, access_token: str, rom: Rom, rom_file: RomFile
    ):
        client.get(
            f"/api/roms/{rom.id}/content/test_rom.zip",
            headers={**_auth(access_token), "Range": "bytes=1024-"},
            follow_redirects=False,
        )

        assert recorded_events() == []

    def test_a_head_request_is_not_a_download(
        self, client: TestClient, access_token: str, rom: Rom, rom_file: RomFile
    ):
        client.head(
            f"/api/roms/{rom.id}/content/test_rom.zip",
            headers=_auth(access_token),
            follow_redirects=False,
        )

        assert recorded_events() == []

    def test_a_failing_recorder_still_serves_the_file(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        rom_file: RomFile,
        mocker,
    ):
        mocker.patch.object(
            db_audit_event_handler, "add_events", side_effect=RuntimeError("down")
        )

        response = client.get(
            f"/api/roms/{rom.id}/content/test_rom.zip",
            headers=_auth(access_token),
            follow_redirects=False,
        )

        assert response.status_code == status.HTTP_200_OK


class TestRomFileContent:
    def _add_file(self, rom: Rom, name: str, category: RomFileCategory) -> RomFile:
        return db_rom_handler.add_rom_file(
            RomFile(
                rom_id=rom.id,
                file_name=name,
                file_path=f"{rom.fs_path}/{rom.fs_name}",
                file_size_bytes=10,
                category=category,
            )
        )

    def test_a_game_file_is_a_download(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        file = self._add_file(rom, "game.bin", RomFileCategory.GAME)

        client.get(
            f"/api/roms/{file.id}/files/content/game.bin",
            headers=_auth(access_token),
        )

        [event] = recorded_events()
        assert event.action == "rom.download"
        assert event.data["file_ids"] == [file.id]

    def test_a_manual_read_in_the_viewer_is_not(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        file = self._add_file(rom, "manual.pdf", RomFileCategory.MANUAL)

        client.get(
            f"/api/roms/{file.id}/files/content/manual.pdf",
            headers=_auth(access_token),
        )

        assert recorded_events() == []


def test_a_bulk_download_is_one_event_on_its_platform(
    client: TestClient, access_token: str, platform: Platform, rom_file: RomFile
):
    response = client.get(
        "/api/roms/download",
        params={"platform_id": platform.id},
        headers=_auth(access_token),
    )

    assert response.status_code == status.HTTP_200_OK
    [event] = recorded_events()
    assert event.action == "rom.bulk_download"
    assert (event.target_type, event.target_id) == ("platform", str(platform.id))
    assert event.data["count"] == 1


def test_someone_elses_private_collection_is_kept_by_id_only(
    client: TestClient,
    access_token: str,
    editor_user: User,
    rom: Rom,
    rom_file: RomFile,
):
    private = db_collection_handler.add_collection(
        Collection(
            name="Secret shelf",
            description="",
            is_public=False,
            is_favorite=False,
            user_id=editor_user.id,
        )
    )
    db_collection_handler.add_roms_to_collection(private.id, [rom.id])

    client.get(
        "/api/roms/download",
        params={"collection_id": private.id},
        headers=_auth(access_token),
    )

    [event] = recorded_events()
    assert (event.target_id, event.target_name) == (str(private.id), None)
