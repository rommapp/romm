"""Cache gating for the gallery sidecars (filter values, char index, id index).

`GET /roms` returns three whole-library aggregates alongside the page. Only the
fully unscoped scan may be memoised under the shared "all" key, because that key
encodes user/order/grouping but none of the filters.

The filter-value list is the exception: it is built from `unfiltered_query` with
only platform / collection / search applied, so the row-level filters (missing,
favorite, duplicate, ...) never reach its query and its result is byte-identical
to the unfiltered one. Locking it out of the cache made the Missing tab recompute
the whole library on every visit, sort change and platform pick (issue #3992).

These tests pin the split gate:
  1. a row-level filter reads and writes the shared filter-values entry,
  2. a scope filter (platform / collection / search) does neither,
  3. the char index and the id index stay live under any row-level filter,
     since both narrow with it.
"""

from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from endpoints.roms import build_unscoped_sidecar_cache_key
from handler.database import db_rom_handler
from handler.database.roms_handler import (
    _filter_values_cache_version,
    _filter_values_redis_key,
    _store_versioned_cache,
)
from handler.redis_handler import sync_cache
from models.platform import Platform
from models.rom import Rom
from models.user import User

# A recognisable filter-value payload: if the endpoint answers with this, it
# read the shared cache entry rather than recomputing over the library.
SENTINEL_FILTER_VALUES: dict[str, Any] = {
    "genres": ["Sentinel Genre"],
    "franchises": [],
    "collections": [],
    "companies": [],
    "game_modes": [],
    "age_ratings": [],
    "player_counts": [],
    "regions": [],
    "languages": [],
    "tags": [],
    "platforms": [],
}


@pytest.fixture
def missing_rom(rom: Rom) -> Rom:
    """Flag the shared rom as missing from the filesystem."""
    db_rom = db_rom_handler.update_rom(rom.id, {"missing_from_fs": True})
    return db_rom


def _unscoped_key(user_id: int) -> str:
    """The shared sidecar key for a default (no order, no grouping) request."""
    key = build_unscoped_sidecar_cache_key(user_id, "", "asc", False, True)
    assert key is not None
    return key


def _seed_filter_values(user_id: int) -> str:
    version = _filter_values_cache_version()
    redis_key = _filter_values_redis_key(_unscoped_key(user_id), version)
    _store_versioned_cache(redis_key, version, SENTINEL_FILTER_VALUES)
    return redis_key


def _get_roms(client: TestClient, access_token: str, **params: Any) -> dict:
    response = client.get(
        "/api/roms",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    assert response.status_code == status.HTTP_200_OK
    return response.json()


def test_row_filter_reads_unscoped_filter_values_cache(
    client: TestClient, access_token: str, admin_user: User, missing_rom: Rom
):
    """`missing=true` reuses the whole-library entry the unfiltered scan wrote."""
    _seed_filter_values(admin_user.id)

    body = _get_roms(client, access_token, missing=True)

    assert body["filter_values"]["genres"] == ["Sentinel Genre"]


def test_row_filter_writes_unscoped_filter_values_cache(
    client: TestClient, access_token: str, admin_user: User, missing_rom: Rom
):
    """A row-filtered request also warms the shared entry for everyone else."""
    version = _filter_values_cache_version()
    redis_key = _filter_values_redis_key(_unscoped_key(admin_user.id), version)
    assert sync_cache.get(redis_key) is None

    _get_roms(client, access_token, missing=True)

    assert sync_cache.get(redis_key) is not None


def test_row_filtered_and_unfiltered_filter_values_match(
    client: TestClient, access_token: str, missing_rom: Rom
):
    """The two are the same list, which is what makes sharing the key correct."""
    filtered = _get_roms(client, access_token, missing=True)
    unfiltered = _get_roms(client, access_token)

    assert filtered["filter_values"] == unfiltered["filter_values"]


def test_platform_scope_does_not_read_unscoped_filter_values_cache(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    """A platform narrows the filter-value list, so it must be computed live."""
    _seed_filter_values(admin_user.id)

    body = _get_roms(client, access_token, platform_ids=platform.id)

    assert body["filter_values"]["genres"] == []


def test_platform_scope_does_not_write_unscoped_filter_values_cache(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    """A scoped list must never leak into the shared whole-library entry."""
    redis_key = _seed_filter_values(admin_user.id)

    _get_roms(client, access_token, platform_ids=platform.id)

    cached = sync_cache.get(redis_key)
    assert cached is not None
    assert b"Sentinel Genre" in (
        cached if isinstance(cached, bytes) else cached.encode()
    )


def test_search_scope_does_not_read_unscoped_filter_values_cache(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """A search term narrows the filter-value list the same way a platform does."""
    _seed_filter_values(admin_user.id)

    body = _get_roms(client, access_token, search_term="nothing-matches-this")

    assert body["filter_values"]["genres"] == []


def test_row_filter_does_not_read_unscoped_char_index_cache(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """The char index counts filtered rows, so the shared entry does not apply."""
    version = _filter_values_cache_version()
    _store_versioned_cache(
        f"char_index:{_unscoped_key(admin_user.id)}:v{version}", version, [["Z", 41]]
    )

    body = _get_roms(client, access_token, missing=True)

    assert "Z" not in body["char_index"]


def test_row_filter_does_not_read_unscoped_rom_id_index_cache(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """Same for the id index: it is the filtered result set, not the library."""
    version = _filter_values_cache_version()
    _store_versioned_cache(
        f"rom_id_index:{_unscoped_key(admin_user.id)}:v{version}", version, [424242]
    )

    body = _get_roms(client, access_token, missing=True)

    assert body["rom_id_index"] == []


def test_unfiltered_request_still_reads_unscoped_char_index_cache(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """The unscoped scan keeps its memoisation (the case the key was built for)."""
    version = _filter_values_cache_version()
    _store_versioned_cache(
        f"char_index:{_unscoped_key(admin_user.id)}:v{version}", version, [["Z", 41]]
    )

    body = _get_roms(client, access_token)

    assert body["char_index"] == {"Z": 41}
