"""Saves, states, screenshots and memory cards on a hidden ROM or platform 404."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.factories import (
    make_esrb_rated_rom,
    make_platform,
    make_rom,
    make_save,
    make_screenshot,
    make_state,
)

from config import OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS
from handler.auth.base_handler import oauth_handler
from handler.database import db_memory_card_handler, db_user_handler
from handler.database.base_handler import sync_session
from models.assets import MemoryCard
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _auth(user: User) -> dict[str, str]:
    token = oauth_handler.create_access_token(
        data={
            "sub": user.username,
            "iss": "romm:oauth",
            "scopes": " ".join(user.oauth_scopes),
        },
        expires_delta=timedelta(seconds=OAUTH_ACCESS_TOKEN_EXPIRE_SECONDS),
    )
    return {"Authorization": f"Bearer {token}"}


def _hide(entity: PermEntity, entity_id: int, user_id: int) -> None:
    with sync_session.begin() as s:
        s.add(HiddenEntity(entity=entity, entity_id=entity_id, user_id=user_id))


def _make_card(user: User, platform_id: int | None, **fields: Any) -> MemoryCard:
    return db_memory_card_handler.add_card(
        MemoryCard(
            user_id=user.id,
            emulator="pcsx2",
            platform_id=platform_id,
            name=fields.pop("name", "card"),
            slot=1,
            **fields,
        )
    )


# (method, path template, json body) for every owner per-id route.
SAVE_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/saves/{id}", None),
    ("POST", "/api/saves/{id}/downloaded", {"device_id": "dev"}),
    ("PUT", "/api/saves/{id}", None),
    ("PUT", "/api/saves/{id}/visibility", {"is_public": True}),
    ("PUT", "/api/saves/{id}/favorite", {"is_favorite": True}),
    ("PUT", "/api/saves/{id}/labels", {"labels": ["a"]}),
    ("PUT", "/api/saves/{id}/file-name", {"file_name": "renamed.sav"}),
    ("POST", "/api/saves/delete", {"saves": ["{id}"]}),
    ("POST", "/api/saves/{id}/track", {"device_id": "dev"}),
    ("POST", "/api/saves/{id}/untrack", {"device_id": "dev"}),
]

STATE_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", "/api/states/{id}", None),
    ("PUT", "/api/states/{id}", None),
    ("PUT", "/api/states/{id}/visibility", {"is_public": True}),
    ("PUT", "/api/states/{id}/favorite", {"is_favorite": True}),
    ("PUT", "/api/states/{id}/labels", {"labels": ["a"]}),
    ("PUT", "/api/states/{id}/file-name", {"file_name": "renamed.state"}),
    ("POST", "/api/states/delete", {"states": ["{id}"]}),
]


def _call(
    client: TestClient,
    user: User,
    method: str,
    path: str,
    body: dict[str, Any] | None,
    asset_id: int,
) -> Any:
    if body is not None:
        body = {
            key: [asset_id] if value == ["{id}"] else value
            for key, value in body.items()
        }
    return client.request(
        method, path.format(id=asset_id), headers=_auth(user), json=body
    )


@pytest.mark.parametrize(("method", "path", "body"), SAVE_ROUTES)
def test_save_routes_404_on_a_hidden_rom(
    client: TestClient,
    editor_user: User,
    rom: Rom,
    method: str,
    path: str,
    body: dict[str, Any] | None,
):
    save = make_save(rom, editor_user, "hidden.sav")
    _hide(PermEntity.ROMS, rom.id, editor_user.id)

    response = _call(client, editor_user, method, path, body, save.id)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == f"Save with ID {save.id} not found"


@pytest.mark.parametrize(("method", "path", "body"), STATE_ROUTES)
def test_state_routes_404_on_a_hidden_rom(
    client: TestClient,
    editor_user: User,
    rom: Rom,
    method: str,
    path: str,
    body: dict[str, Any] | None,
):
    state = make_state(rom, editor_user, "hidden.state")
    _hide(PermEntity.ROMS, rom.id, editor_user.id)

    response = _call(client, editor_user, method, path, body, state.id)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == f"State with ID {state.id} not found"


def test_a_save_on_a_visible_rom_still_updates(
    client: TestClient, editor_user: User, rom: Rom
):
    save = make_save(rom, editor_user, "visible.sav")

    response = client.put(
        f"/api/saves/{save.id}/favorite",
        headers=_auth(editor_user),
        json={"is_favorite": True},
    )

    assert response.status_code == status.HTTP_200_OK


def test_a_save_on_a_hidden_platform_is_404(
    client: TestClient, editor_user: User, platform: Platform, rom: Rom
):
    save = make_save(rom, editor_user, "hidden.sav")
    _hide(PermEntity.PLATFORMS, platform.id, editor_user.id)

    response = client.get(f"/api/saves/{save.id}", headers=_auth(editor_user))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_a_save_above_the_age_limit_is_404_and_left_out(
    client: TestClient, editor_user: User, platform: Platform
):
    mature = make_esrb_rated_rom(platform, "Mature", "M")
    everyone = make_esrb_rated_rom(platform, "Everyone", "E")
    hidden = make_save(mature, editor_user, "mature.sav")
    kept = make_save(everyone, editor_user, "everyone.sav")
    db_user_handler.update_user(editor_user.id, {"age_limit": 12})

    detail = client.get(f"/api/saves/{hidden.id}", headers=_auth(editor_user))
    assert detail.status_code == status.HTTP_404_NOT_FOUND

    listing = client.get("/api/saves", headers=_auth(editor_user)).json()
    assert [s["id"] for s in listing] == [kept.id]


def test_save_lists_leave_out_hidden_roms(
    client: TestClient, editor_user: User, platform: Platform, rom: Rom
):
    hidden_rom = make_rom(platform, "hidden")
    kept = [make_save(rom, editor_user, f"kept{i}.sav") for i in range(2)]
    hidden = make_save(hidden_rom, editor_user, "hidden.sav")
    _hide(PermEntity.ROMS, hidden_rom.id, editor_user.id)
    kept_ids = {s.id for s in kept}

    listing = client.get("/api/saves", headers=_auth(editor_user)).json()
    assert {s["id"] for s in listing} == kept_ids

    scoped = client.get(
        f"/api/saves?platform_id={platform.id}", headers=_auth(editor_user)
    ).json()
    assert {s["id"] for s in scoped} == kept_ids

    ids = client.get("/api/saves/identifiers", headers=_auth(editor_user)).json()
    assert hidden.id not in ids
    assert set(ids) == kept_ids


def test_saves_summary_is_404_on_a_hidden_rom(
    client: TestClient, editor_user: User, rom: Rom
):
    make_save(rom, editor_user, "hidden.sav")
    _hide(PermEntity.ROMS, rom.id, editor_user.id)

    response = client.get(
        f"/api/saves/summary?rom_id={rom.id}", headers=_auth(editor_user)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_state_lists_leave_out_hidden_platforms(
    client: TestClient, editor_user: User, rom: Rom
):
    hidden_platform = make_platform("snes")
    hidden_rom = make_rom(hidden_platform, "hidden")
    kept = make_state(rom, editor_user, "kept.state")
    make_state(hidden_rom, editor_user, "hidden.state")
    _hide(PermEntity.PLATFORMS, hidden_platform.id, editor_user.id)

    listing = client.get("/api/states", headers=_auth(editor_user)).json()
    assert [s["id"] for s in listing] == [kept.id]

    ids = client.get("/api/states/identifiers", headers=_auth(editor_user)).json()
    assert ids == [kept.id]


def test_admin_lists_are_unrestricted(
    client: TestClient, admin_user: User, platform: Platform, rom: Rom
):
    save = make_save(rom, admin_user, "admin.sav")
    _hide(PermEntity.PLATFORMS, platform.id, admin_user.id)

    listing = client.get("/api/saves", headers=_auth(admin_user)).json()

    assert [s["id"] for s in listing] == [save.id]


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_screenshot_writes_404_on_a_hidden_rom(
    client: TestClient, editor_user: User, rom: Rom, method: str
):
    screenshot = make_screenshot(rom, editor_user, "hidden.png")
    _hide(PermEntity.ROMS, rom.id, editor_user.id)

    response = client.request(
        method,
        f"/api/screenshots/{screenshot.id}",
        headers=_auth(editor_user),
        json={"is_public": True} if method == "PUT" else None,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_memory_card_create_on_a_hidden_platform_is_404(
    client: TestClient, editor_user: User, platform: Platform
):
    _hide(PermEntity.PLATFORMS, platform.id, editor_user.id)

    response = client.post(
        "/api/memory-cards",
        headers=_auth(editor_user),
        json={"name": "card", "emulator": "pcsx2", "platform_id": platform.id},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == f"Platform with ID {platform.id} not found"


def test_memory_card_lists_leave_out_hidden_platforms(
    client: TestClient, editor_user: User, admin_user: User, platform: Platform
):
    hidden_platform = make_platform("snes")
    own = _make_card(editor_user, platform.id, name="own")
    loose = _make_card(editor_user, None, name="loose")
    _make_card(editor_user, hidden_platform.id, name="hidden")
    shared = _make_card(admin_user, platform.id, name="shared", is_public=True)
    _make_card(admin_user, hidden_platform.id, name="shared_hidden", is_public=True)
    _hide(PermEntity.PLATFORMS, hidden_platform.id, editor_user.id)

    listing = client.get("/api/memory-cards", headers=_auth(editor_user)).json()
    assert {c["id"] for c in listing} == {own.id, loose.id}

    shared_listing = client.get(
        "/api/memory-cards/shared?emulator=pcsx2", headers=_auth(editor_user)
    ).json()
    assert {c["id"] for c in shared_listing} == {own.id, loose.id, shared.id}


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/api/memory-cards/{id}", None),
        ("GET", "/api/memory-cards/{id}/content", None),
        ("GET", "/api/memory-cards/{id}/versions", None),
        ("PUT", "/api/memory-cards/{id}", {"name": "renamed"}),
        ("PUT", "/api/memory-cards/{id}/visibility", {"is_public": True}),
        ("POST", "/api/memory-cards/delete", {"cards": ["{id}"]}),
    ],
)
def test_memory_card_routes_404_on_a_hidden_platform(
    client: TestClient,
    editor_user: User,
    platform: Platform,
    method: str,
    path: str,
    body: dict[str, Any] | None,
):
    card = _make_card(editor_user, platform.id)
    _hide(PermEntity.PLATFORMS, platform.id, editor_user.id)

    response = _call(client, editor_user, method, path, body, card.id)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == f"Memory card with ID {card.id} not found"


def test_a_platformless_memory_card_stays_readable(
    client: TestClient, editor_user: User, platform: Platform
):
    card = _make_card(editor_user, None)
    _hide(PermEntity.PLATFORMS, platform.id, editor_user.id)

    response = client.get(f"/api/memory-cards/{card.id}", headers=_auth(editor_user))

    assert response.status_code == status.HTTP_200_OK
