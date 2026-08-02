"""Tests for `GET /api/roms/random` (issue #4066).

The endpoint replaces the two-call "count the library, then fetch the row at a
random offset" dance the Home widget used to run. Paging to a random offset
costs more the bigger the library gets, so these tests pin both the behaviour
(a rom from the requested scope, every rom reachable) and the mechanism (no
offset walk, no full count).
"""

from collections import Counter
from typing import Iterator
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import event

from handler.database import (
    db_collection_handler,
    db_platform_handler,
    db_rom_handler,
    roms_handler,
)
from handler.database.base_handler import sync_engine, sync_session
from models.collection import Collection
from models.permission import HiddenEntity, PermEntity
from models.platform import Platform
from models.rom import Rom
from models.user import User


def _add_rom(platform: Platform, name: str) -> Rom:
    return db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=name,
            slug=name,
            fs_name=f"{name}.zip",
            fs_name_no_tags=name,
            fs_name_no_ext=name,
            fs_extension="zip",
            fs_path=f"{platform.slug}/roms",
        )
    )


@pytest.fixture
def other_platform() -> Platform:
    return db_platform_handler.add_platform(
        Platform(
            name="other_platform",
            slug="other_platform_slug",
            fs_slug="other_platform_slug",
        )
    )


@pytest.fixture
def captured_sql() -> Iterator[list[str]]:
    """Every statement the engine runs while the fixture is active."""
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, many):
        statements.append(statement)

    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)


def test_get_random_rom_returns_a_rom(
    client: TestClient, access_token: str, rom: Rom
) -> None:
    response = client.get(
        "/api/roms/random",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert body is not None
    assert body["id"] == rom.id
    # The widget renders cover, platform and release year straight off the pick.
    assert body["platform_slug"] == rom.platform_slug


def test_get_random_rom_requires_auth(client: TestClient) -> None:
    response = client.get("/api/roms/random")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_random_rom_without_roms_returns_null(
    client: TestClient, access_token: str, platform: Platform
) -> None:
    """An empty library is not an error: the widget shows its own empty copy."""
    response = client.get(
        "/api/roms/random",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() is None


def test_get_random_rom_reaches_every_rom(
    client: TestClient, access_token: str, rom: Rom, platform: Platform
) -> None:
    """Sampling must cover the whole set, not park on one end of it."""
    ids = {rom.id} | {_add_rom(platform, f"rom_{i}").id for i in range(4)}

    seen: Counter[int] = Counter()
    for _ in range(120):
        response = client.get(
            "/api/roms/random",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        seen[response.json()["id"]] += 1

    assert set(seen) == ids


def test_get_random_rom_scoped_to_platform(
    client: TestClient,
    access_token: str,
    rom: Rom,
    platform: Platform,
    other_platform: Platform,
) -> None:
    other_ids = {_add_rom(other_platform, f"other_{i}").id for i in range(3)}

    for _ in range(20):
        response = client.get(
            "/api/roms/random",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"platform_ids": [other_platform.id]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] in other_ids

    response = client.get(
        "/api/roms/random",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"platform_ids": [platform.id]},
    )
    assert response.json()["id"] == rom.id


def test_get_random_rom_scoped_to_collection(
    client: TestClient,
    access_token: str,
    admin_user: User,
    rom: Rom,
    platform: Platform,
) -> None:
    in_collection = _add_rom(platform, "in_collection")
    _add_rom(platform, "out_of_collection")

    collection = db_collection_handler.add_collection(
        Collection(name="Picks", description="", user_id=admin_user.id)
    )
    db_collection_handler.add_roms_to_collection(collection.id, [in_collection.id])

    for _ in range(10):
        response = client.get(
            "/api/roms/random",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"collection_id": collection.id},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == in_collection.id


def test_get_random_rom_scoped_to_empty_collection_returns_null(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
) -> None:
    """No sampled key can land in an empty scope, so this is the fallback's null."""
    collection = db_collection_handler.add_collection(
        Collection(name="Empty", description="", user_id=admin_user.id)
    )

    response = client.get(
        "/api/roms/random",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"collection_id": collection.id},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() is None


def test_get_random_rom_skips_hidden_roms(
    client: TestClient,
    viewer_user: User,
    viewer_access_token: str,
    rom: Rom,
    platform: Platform,
) -> None:
    """Admin-hidden roms are out of scope for the pick, like any other list."""
    visible = _add_rom(platform, "visible_rom")
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(
                entity=PermEntity.ROMS, entity_id=rom.id, user_id=viewer_user.id
            )
        )

    for _ in range(30):
        response = client.get(
            "/api/roms/random",
            headers={"Authorization": f"Bearer {viewer_access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["id"] == visible.id


def test_get_random_rom_rechecks_visibility_after_fetching(
    client: TestClient,
    viewer_user: User,
    viewer_access_token: str,
    rom: Rom,
    platform: Platform,
) -> None:
    """The pick is re-checked against the row that came back, not the filter.

    The id is chosen by a filtered query but fetched by raw id, so a rom that
    moved to a hidden platform in between would arrive hidden. Standing in for
    that race by handing the endpoint a rom the filter would have excluded.
    """
    # A visible rom so the pick resolves an id, otherwise the empty scope
    # returns null on its own and the fetch is never reached.
    _add_rom(platform, "visible_rom")
    with sync_session.begin() as session:
        session.add(
            HiddenEntity(
                entity=PermEntity.ROMS, entity_id=rom.id, user_id=viewer_user.id
            )
        )

    with patch.object(db_rom_handler, "get_rom_simple", return_value=rom):
        response = client.get(
            "/api/roms/random",
            headers={"Authorization": f"Bearer {viewer_access_token}"},
        )

    assert response.status_code == status.HTTP_200_OK
    # Null, not 404: a hidden rom stays indistinguishable from an empty scope.
    assert response.json() is None


def test_get_random_rom_does_not_page_or_count(
    client: TestClient,
    access_token: str,
    rom: Rom,
    platform: Platform,
    captured_sql: list[str],
) -> None:
    """The point of the endpoint: cost that doesn't grow with the library.

    Both mechanisms it replaces walk the whole filtered set: an OFFSET steps
    over every preceding row, and the total was its own count of the library.
    Sampling primary keys does neither, and consecutively-numbered roms always
    land it a hit.
    """
    for i in range(5):
        _add_rom(platform, f"rom_{i}")
    captured_sql.clear()

    with (
        patch.object(
            db_rom_handler, "get_rom_count", wraps=db_rom_handler.get_rom_count
        ) as get_rom_count,
        patch.object(
            db_rom_handler, "get_rom_id_index", wraps=db_rom_handler.get_rom_id_index
        ) as get_rom_id_index,
    ):
        response = client.get(
            "/api/roms/random",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == status.HTTP_200_OK

        get_rom_count.assert_not_called()
        get_rom_id_index.assert_not_called()

    rom_queries = [sql for sql in captured_sql if " roms" in sql.lower()]
    assert rom_queries, "expected the pick to query the roms table"
    assert not [sql for sql in rom_queries if "offset" in sql.lower()]


def test_get_random_rom_falls_back_when_sampling_misses(
    client: TestClient, access_token: str, rom: Rom, platform: Platform
) -> None:
    """A scope the sampled keys never hit still resolves a pick.

    Sampling zero keys stands in for the real cases: a narrow filter, or an id
    space left sparse by deletions.
    """
    ids = {rom.id} | {_add_rom(platform, f"rom_{i}").id for i in range(4)}

    seen: set[int] = set()
    with patch.object(roms_handler, "RANDOM_ID_SAMPLE_SIZE", 0):
        for _ in range(120):
            response = client.get(
                "/api/roms/random",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert response.status_code == status.HTTP_200_OK
            seen.add(response.json()["id"])

    # The fallback is a position in the set, so it reaches all of it too.
    assert seen == ids
