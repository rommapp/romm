from typing import Any, cast

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.auth_helpers import hide, user_headers
from tests.factories import make_platform, make_rom

from handler.database import db_rom_handler
from models.permission import PermEntity
from models.platform import Platform
from models.user import User
from utils.validation import MAX_ROM_IDS_PER_QUERY


def _get(
    client: TestClient, headers: dict[str, str], **params: Any
) -> tuple[int, dict[str, Any]]:
    response = client.get("/api/roms", headers=headers, params=params)
    return response.status_code, cast(dict[str, Any], response.json())


def _ids(page: dict[str, Any]) -> list[int]:
    return [item["id"] for item in page["items"]]


def test_a_window_by_id_keeps_the_order_given(
    client: TestClient, headers: dict[str, str], platform: Platform
):
    # Arrange
    roms = [make_rom(platform, name) for name in ("alpha", "bravo", "charlie")]
    wanted = [roms[2].id, roms[0].id, roms[1].id]

    # Act
    code, page = _get(client, headers, rom_ids=wanted)

    # Assert
    assert code == status.HTTP_200_OK
    assert _ids(page) == wanted
    assert page["total"] is None
    assert page["rom_id_index"] == []
    assert page["char_index"] == {}
    assert (page["offset"], page["limit"]) == (0, len(wanted))


def test_a_repeated_id_is_loaded_once(
    client: TestClient, headers: dict[str, str], platform: Platform
):
    # Arrange
    first, second = make_rom(platform, "india"), make_rom(platform, "juliett")

    # Act
    _, page = _get(
        client,
        headers,
        rom_ids=[second.id, first.id, second.id],
    )

    # Assert
    assert _ids(page) == [second.id, first.id]


def test_a_window_by_id_skips_the_grouped_page_cache(
    client: TestClient,
    headers: dict[str, str],
    platform: Platform,
    monkeypatch: pytest.MonkeyPatch,
):
    # Arrange
    rom = make_rom(platform, "kilo")
    calls: list[str] = []
    monkeypatch.setattr(
        db_rom_handler,
        "get_cached_rom_id_page",
        lambda *args: calls.append("page"),
    )

    # Act
    _, page = _get(
        client,
        headers,
        rom_ids=[rom.id],
        group_by_meta_id="true",
    )

    # Assert
    assert _ids(page) == [rom.id]
    assert calls == []


def test_a_window_by_id_matches_the_window_by_offset(
    client: TestClient, headers: dict[str, str], platform: Platform
):
    # Arrange
    for name in ("delta", "echo", "foxtrot", "golf", "hotel"):
        make_rom(platform, name)
    _, first = _get(client, headers, order_by="name", limit=72)
    window = first["rom_id_index"][1:4]

    # Act
    _, by_offset = _get(
        client,
        headers,
        order_by="name",
        offset=1,
        limit=3,
        with_rom_id_index="false",
        with_total="false",
    )
    _, by_id = _get(client, headers, order_by="name", rom_ids=window)

    # Assert
    assert _ids(by_offset) == window
    assert _ids(by_id) == window


def test_a_hidden_rom_is_left_out_of_a_window_by_id(
    client: TestClient, viewer_user: User, platform: Platform
):
    # Arrange
    shown = make_rom(platform, "shown")
    hidden = make_rom(platform, "hidden")
    hide(PermEntity.ROMS, hidden.id, user_id=viewer_user.id)

    # Act
    code, page = _get(client, user_headers(viewer_user), rom_ids=[hidden.id, shown.id])

    # Assert
    assert code == status.HTTP_200_OK
    assert _ids(page) == [shown.id]


def test_a_rom_on_a_hidden_platform_is_left_out_of_a_window_by_id(
    client: TestClient, viewer_user: User, platform: Platform
):
    # Arrange
    shown = make_rom(platform, "shown")
    hidden_platform = make_platform("hidden-platform")
    hidden = make_rom(hidden_platform, "hidden")
    hide(PermEntity.PLATFORMS, hidden_platform.id, user_id=viewer_user.id)

    # Act
    _, page = _get(client, user_headers(viewer_user), rom_ids=[hidden.id, shown.id])

    # Assert
    assert _ids(page) == [shown.id]


def test_a_deleted_rom_is_left_out_of_a_window_by_id(
    client: TestClient, headers: dict[str, str], platform: Platform
):
    # Arrange
    kept = make_rom(platform, "kept")
    gone = make_rom(platform, "gone")
    db_rom_handler.delete_rom(gone.id)

    # Act
    _, page = _get(
        client,
        headers,
        rom_ids=[gone.id, kept.id],
    )

    # Assert
    assert _ids(page) == [kept.id]


def test_the_window_holds_up_to_the_cap_whatever_the_limit(
    client: TestClient, headers: dict[str, str], platform: Platform
):
    # Arrange
    rom = make_rom(platform, "only")
    wanted = [rom.id, *range(10_000_000, 10_000_000 + MAX_ROM_IDS_PER_QUERY - 1)]

    # Act
    code, page = _get(client, headers, rom_ids=wanted, limit=2)

    # Assert
    assert code == status.HTTP_200_OK
    assert _ids(page) == [rom.id]


@pytest.mark.parametrize(
    "rom_ids",
    [
        list(range(1, MAX_ROM_IDS_PER_QUERY + 2)),
        [0],
        [-5],
        ["abc"],
    ],
    ids=["over the cap", "zero", "negative", "not a number"],
)
def test_an_invalid_window_is_refused(
    client: TestClient, headers: dict[str, str], rom_ids: list[Any]
):
    # Act
    code, body = _get(client, headers, rom_ids=rom_ids)

    # Assert
    assert code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert any("rom_ids" in error["loc"] for error in body["detail"])
