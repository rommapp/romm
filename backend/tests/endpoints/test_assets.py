from unittest import mock

from fastapi import status
from fastapi.testclient import TestClient
from tests.factories import make_save, make_screenshot, make_state

from handler.database import db_deleted_asset_handler
from models.assets import Save
from models.platform import Platform
from models.rom import Rom
from models.user import User


def test_delete_saves(client, access_token, save):
    response = client.post(
        "/api/saves/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"saves": [save.id]},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert len(body) == 1

    # No hash and no file to take one from, so nothing a device could match.
    assert not any(
        record.content_hashes
        for record in db_deleted_asset_handler.get_deletions(
            user_id=save.user_id, rom_ids=[save.rom_id]
        )
    )


def test_delete_saves_hashes_a_save_that_never_recorded_one(
    client, access_token, save: Save
):
    assert save.content_hash is None

    with mock.patch(
        "endpoints.saves.fs_asset_handler.compute_content_hash",
        new=mock.AsyncMock(return_value="deadbeef"),
    ) as compute_content_hash:
        response = client.post(
            "/api/saves/delete",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"saves": [save.id]},
        )

    assert response.status_code == status.HTTP_200_OK
    compute_content_hash.assert_awaited_once_with(save.full_path)
    [record] = db_deleted_asset_handler.get_deletions(
        user_id=save.user_id, rom_ids=[save.rom_id]
    )
    assert record.content_hashes == ["deadbeef"]


def test_delete_states(client, access_token, state):
    response = client.post(
        "/api/states/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"states": [state.id]},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert len(body) == 1


def test_get_states_prefers_exact_matching_screenshot_filename(
    client: TestClient,
    access_token: str,
    rom: Rom,
    platform: Platform,
    admin_user: User,
):
    state_1 = make_state(
        rom,
        admin_user,
        "test_game.state1",
        emulator="retroarch",
        file_path=f"{platform.slug}/states/retroarch",
        file_size_bytes=1,
    )
    state_2 = make_state(
        rom,
        admin_user,
        "test_game.state2",
        emulator="retroarch",
        file_path=f"{platform.slug}/states/retroarch",
        file_size_bytes=1,
    )

    # Ambiguous fallback screenshot stem (`test_game`) that used to be picked for both.
    make_screenshot(
        rom,
        admin_user,
        "test_game.state.auto.png",
        file_extension="png",
        file_size_bytes=1,
    )
    for file_name in ("test_game.state1.png", "test_game.state2.png"):
        make_screenshot(rom, admin_user, file_name, file_size_bytes=1)

    response = client.get(
        "/api/states",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rom_id": rom.id},
    )
    assert response.status_code == status.HTTP_200_OK

    states_by_id = {item["id"]: item for item in response.json()}
    assert states_by_id[state_1.id]["screenshot"]["file_name"] == "test_game.state1.png"
    assert states_by_id[state_2.id]["screenshot"]["file_name"] == "test_game.state2.png"


def test_get_states_screenshot_match_is_scoped_by_user(
    client: TestClient,
    access_token: str,
    rom: Rom,
    platform: Platform,
    admin_user: User,
    editor_user: User,
):
    state = make_state(
        rom,
        admin_user,
        "test_game.state1",
        emulator="retroarch",
        file_path=f"{platform.slug}/states/retroarch",
        file_size_bytes=1,
    )

    for user in [editor_user, admin_user]:
        make_screenshot(rom, user, "test_game.state1.png", file_size_bytes=1)

    response = client.get(
        f"/api/states/{state.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["screenshot"]["user_id"] == admin_user.id


def test_get_saves_prefers_exact_matching_screenshot_filename(
    client: TestClient,
    access_token: str,
    rom: Rom,
    platform: Platform,
    admin_user: User,
):
    save_1 = make_save(
        rom,
        admin_user,
        "test_game.state1",
        emulator="retroarch",
        file_path=f"{platform.slug}/saves/retroarch",
        file_size_bytes=1,
    )
    save_2 = make_save(
        rom,
        admin_user,
        "test_game.state2",
        emulator="retroarch",
        file_path=f"{platform.slug}/saves/retroarch",
        file_size_bytes=1,
    )

    make_screenshot(
        rom,
        admin_user,
        "test_game.state.auto.png",
        file_extension="png",
        file_size_bytes=1,
    )
    for file_name in ("test_game.state1.png", "test_game.state2.png"):
        make_screenshot(rom, admin_user, file_name, file_size_bytes=1)

    response = client.get(
        "/api/saves",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rom_id": rom.id},
    )
    assert response.status_code == status.HTTP_200_OK

    saves_by_id = {item["id"]: item for item in response.json()}
    assert saves_by_id[save_1.id]["screenshot"]["file_name"] == "test_game.state1.png"
    assert saves_by_id[save_2.id]["screenshot"]["file_name"] == "test_game.state2.png"


def test_get_saves_flags_zipped_saves(
    client: TestClient,
    access_token: str,
    rom: Rom,
    platform: Platform,
    admin_user: User,
):
    names = ("game [retroarch a].saves.zip", "GAME.ZIP", "game.srm")
    for file_name in names:
        make_save(
            rom,
            admin_user,
            file_name,
            emulator="retroarch",
            file_path=f"{platform.slug}/saves/retroarch",
            file_size_bytes=1,
        )

    response = client.get(
        "/api/saves",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rom_id": rom.id},
    )
    assert response.status_code == status.HTTP_200_OK

    zipped = {item["file_name"]: item["is_zipped"] for item in response.json()}
    assert zipped == {names[0]: True, names[1]: True, names[2]: False}
