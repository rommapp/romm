import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.factories import make_rom

from endpoints.roms import easyrpg
from handler.database import db_rom_handler
from handler.database.base_handler import sync_session
from handler.easyrpg import easyrpg_handler
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom, RomFile
from models.user import User


def _make_game(admin_user: User, platform: Platform, *paths: str) -> Rom:
    rom = make_rom(platform, "Yume Nikki", fs_extension="")
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    for path in paths:
        folder, _, name = f"{rom.full_path}/{path}".rpartition("/")
        db_rom_handler.add_rom_file(
            RomFile(rom_id=rom.id, file_name=name, file_path=folder, file_size_bytes=1)
        )
    return rom


@pytest.fixture
def game(admin_user: User, platform: Platform) -> Rom:
    return _make_game(admin_user, platform, "RPG_RT.ldb", "Music/Town.mid")


@pytest.fixture
def rtp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        easyrpg_handler.__dict__, "rtp_files", {"Music": ["Battle 1.mid"]}
    )


def test_index_maps_the_games_files(client: TestClient, headers, game: Rom, rtp):
    response = client.get(f"/api/roms/{game.id}/easyrpg/index.json", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["cache-control"] == "no-store"
    cache = response.json()["cache"]
    assert cache["rpg_rt.ldb"] == "RPG_RT.ldb"
    assert cache["music"]["town"] == "Town.mid"
    assert cache["music"]["戦闘1"] == "Battle 1.mid"


def test_game_files_are_handed_to_nginx(client: TestClient, headers, game: Rom):
    response = client.get(
        f"/api/roms/{game.id}/easyrpg/Music/Town.mid", headers=headers
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["x-accel-redirect"] == (
        f"/library/{game.full_path}/Music/Town.mid".replace(" ", "%20")
    )


def test_rtp_files_are_served_from_the_player_assets(
    client: TestClient, headers, game: Rom, rtp
):
    response = client.get(
        f"/api/roms/{game.id}/easyrpg/Music/Battle 1.mid", headers=headers
    )

    assert response.status_code == status.HTTP_200_OK
    assert (
        response.headers["x-accel-redirect"]
        == "/assets/easyrpg/rtp/Music/Battle%201.mid"
    )


@pytest.mark.parametrize("path", ["Music/Missing.mid", "../other/RPG_RT.ldb"])
def test_unknown_paths_are_not_found(client: TestClient, headers, game: Rom, path):
    response = client.get(f"/api/roms/{game.id}/easyrpg/{path}", headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_a_folder_without_a_game_database_is_not_found(
    client: TestClient, headers, admin_user: User, platform: Platform
):
    rom = _make_game(admin_user, platform, "game.bin")

    response = client.get(f"/api/roms/{rom.id}/easyrpg/index.json", headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_a_hidden_game_is_not_found(
    client: TestClient, editor_headers, editor_user: User, game: Rom
):
    with sync_session.begin() as s:
        s.add(
            HiddenEntity(
                entity=PermEntity.ROMS, entity_id=game.id, user_id=editor_user.id
            )
        )

    response = client.get(
        f"/api/roms/{game.id}/easyrpg/index.json", headers=editor_headers
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_is_not_found_while_disabled(mocker, client: TestClient, headers, game: Rom):
    mocker.patch.object(easyrpg, "DISABLE_EASYRPG", True)

    response = client.get(f"/api/roms/{game.id}/easyrpg/index.json", headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_requires_authentication(client: TestClient, game: Rom):
    response = client.get(f"/api/roms/{game.id}/easyrpg/index.json")

    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )
