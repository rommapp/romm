import pytest
from fastapi import status
from fastapi.testclient import TestClient
from main import app

from handler.database import db_save_handler, db_screenshot_handler, db_state_handler
from models.assets import Save, Screenshot, State
from models.platform import Platform
from models.rom import Rom
from models.user import User


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def test_delete_saves(client, access_token, save):
    response = client.post(
        "/api/saves/delete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"saves": [save.id]},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert len(body) == 1


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
    state_1 = db_state_handler.add_state(
        State(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_game.state1",
            file_name_no_tags="test_game",
            file_name_no_ext="test_game",
            file_extension="state1",
            emulator="retroarch",
            file_path=f"{platform.slug}/states/retroarch",
            file_size_bytes=1,
        )
    )
    state_2 = db_state_handler.add_state(
        State(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_game.state2",
            file_name_no_tags="test_game",
            file_name_no_ext="test_game",
            file_extension="state2",
            emulator="retroarch",
            file_path=f"{platform.slug}/states/retroarch",
            file_size_bytes=1,
        )
    )

    # Ambiguous fallback screenshot stem (`test_game`) that used to be picked for both.
    screenshots_data = [
        {
            "file_name": "test_game.state.auto.png",
            "file_name_no_tags": "test_game",
            "file_name_no_ext": "test_game",
        },
        {
            "file_name": "test_game.state1.png",
            "file_name_no_tags": "test_game.state1",
            "file_name_no_ext": "test_game.state1",
        },
        {
            "file_name": "test_game.state2.png",
            "file_name_no_tags": "test_game.state2",
            "file_name_no_ext": "test_game.state2",
        },
    ]

    for data in screenshots_data:
        db_screenshot_handler.add_screenshot(
            Screenshot(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_extension="png",
                file_path=f"{platform.slug}/screenshots",
                file_size_bytes=1,
                **data,
            )
        )

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
    state = db_state_handler.add_state(
        State(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_game.state1",
            file_name_no_tags="test_game",
            file_name_no_ext="test_game",
            file_extension="state1",
            emulator="retroarch",
            file_path=f"{platform.slug}/states/retroarch",
            file_size_bytes=1,
        )
    )

    for user in [editor_user, admin_user]:
        db_screenshot_handler.add_screenshot(
            Screenshot(
                rom_id=rom.id,
                user_id=user.id,
                file_name="test_game.state1.png",
                file_name_no_tags="test_game.state1",
                file_name_no_ext="test_game.state1",
                file_extension="png",
                file_path=f"{platform.slug}/screenshots",
                file_size_bytes=1,
            )
        )

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
    save_1 = db_save_handler.add_save(
        Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_game.state1",
            file_name_no_tags="test_game",
            file_name_no_ext="test_game",
            file_extension="state1",
            emulator="retroarch",
            file_path=f"{platform.slug}/saves/retroarch",
            file_size_bytes=1,
        )
    )
    save_2 = db_save_handler.add_save(
        Save(
            rom_id=rom.id,
            user_id=admin_user.id,
            file_name="test_game.state2",
            file_name_no_tags="test_game",
            file_name_no_ext="test_game",
            file_extension="state2",
            emulator="retroarch",
            file_path=f"{platform.slug}/saves/retroarch",
            file_size_bytes=1,
        )
    )

    screenshots_data = [
        {
            "file_name": "test_game.state.auto.png",
            "file_name_no_tags": "test_game",
            "file_name_no_ext": "test_game",
        },
        {
            "file_name": "test_game.state1.png",
            "file_name_no_tags": "test_game.state1",
            "file_name_no_ext": "test_game.state1",
        },
        {
            "file_name": "test_game.state2.png",
            "file_name_no_tags": "test_game.state2",
            "file_name_no_ext": "test_game.state2",
        },
    ]

    for data in screenshots_data:
        db_screenshot_handler.add_screenshot(
            Screenshot(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_extension="png",
                file_path=f"{platform.slug}/screenshots",
                file_size_bytes=1,
                **data,
            )
        )

    response = client.get(
        "/api/saves",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"rom_id": rom.id},
    )
    assert response.status_code == status.HTTP_200_OK

    saves_by_id = {item["id"]: item for item in response.json()}
    assert saves_by_id[save_1.id]["screenshot"]["file_name"] == "test_game.state1.png"
    assert saves_by_id[save_2.id]["screenshot"]["file_name"] == "test_game.state2.png"
