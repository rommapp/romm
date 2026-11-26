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
     since both narrow with it,
  4. RomUser-column sorts key on a per-user sort version, so a rom_user
     write refreshes that user's sorted index without touching other
     users' entries or the name-sorted one, and `hidden` still bumps
     globally,
  5. grouped sets key on a per-user sibling version moved only by
     main-sibling picks, and filter values use one order-free per-user
     entry,
  6. grouped pages read their window of the id list the index request
     cached, which a grouped single-platform set also caches, under a key
     naming its platform.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, cast

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from tests.factories import make_rom

from endpoints.roms import (
    build_grouped_page_cache_key,
    build_unscoped_sidecar_cache_key,
)
from handler.database import db_rom_handler
from handler.database.roms_handler import (
    _char_index_redis_key,
    _filter_values_cache_keys_key,
    _filter_values_cache_version,
    _rom_id_index_redis_key,
    _store_versioned_cache,
    _store_versioned_id_list,
)
from handler.redis_handler import as_text, sync_cache
from models.platform import Platform
from models.rom import Rom
from models.user import User


@pytest.fixture
def missing_rom(rom: Rom) -> Rom:
    """Flag the shared rom as missing from the filesystem."""
    db_rom = db_rom_handler.update_rom(rom.id, {"missing_from_fs": True})
    return db_rom


def _unscoped_key(
    user_id: int, order_by: str = "", order_dir: str = "asc", group: bool = False
) -> str:
    """The shared sidecar key for an unscoped request."""
    key = build_unscoped_sidecar_cache_key(user_id, order_by, order_dir, group, True)
    assert key is not None
    return key


def _platform_key(user_id: int, platform_id: int) -> str:
    """The sidecar key for a grouped, default-ordered platform gallery."""
    return build_grouped_page_cache_key(user_id, "", "asc", platform_id)


def _seed_rom_id_index(cache_key: str, ids: list[int]) -> str:
    version = _filter_values_cache_version()
    redis_key = _rom_id_index_redis_key(cache_key, version)
    _store_versioned_id_list(redis_key, version, ids)
    return redis_key


def _get_roms(client: TestClient, access_token: str, **params: Any) -> dict[str, Any]:
    response = client.get(
        "/api/roms",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    assert response.status_code == status.HTTP_200_OK
    return cast(dict[str, Any], response.json())


def test_row_filter_does_not_read_unscoped_char_index_cache(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """The char index counts filtered rows, so the shared entry does not apply."""
    version = _filter_values_cache_version()
    _store_versioned_cache(
        _char_index_redis_key(_unscoped_key(admin_user.id), version),
        version,
        [["Z", 41]],
    )

    body = _get_roms(client, access_token, missing=True)

    assert "Z" not in body["char_index"]


def test_row_filter_does_not_read_unscoped_rom_id_index_cache(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """Same for the id index: it is the filtered result set, not the library."""
    _seed_rom_id_index(_unscoped_key(admin_user.id), [424242])

    body = _get_roms(client, access_token, missing=True)

    assert body["rom_id_index"] == []


def test_length_filter_does_not_read_unscoped_rom_id_index_cache(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """A HowLongToBeat range narrows the result set like any other row filter."""
    _seed_rom_id_index(_unscoped_key(admin_user.id), [424242])

    body = _get_roms(client, access_token, hltb_main_story_max=3600)

    assert body["rom_id_index"] == []


def test_unfiltered_request_still_reads_unscoped_char_index_cache(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """The unscoped scan keeps its memoisation (the case the key was built for)."""
    version = _filter_values_cache_version()
    _store_versioned_cache(
        _char_index_redis_key(_unscoped_key(admin_user.id), version),
        version,
        [["Z", 41]],
    )

    body = _get_roms(client, access_token)

    assert body["char_index"] == {"Z": 41}


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        # Relevance leads, so the rows run in no letter order.
        ({"search_term": "final fantasy"}, {}),
        ({"search_term": "final fantasy", "order_by": "name"}, {"f": 0}),
        ({"search_term": "fantasy"}, {}),
        # Too short to rank, so the name order stands.
        ({"search_term": "fa"}, {"f": 0}),
        ({}, {"f": 0}),
    ],
)
def test_char_index_follows_whether_relevance_leads(
    client: TestClient,
    access_token: str,
    platform: Platform,
    params: dict[str, str],
    expected: dict[str, int],
):
    make_rom(platform, "Final Fantasy")
    make_rom(platform, "Final Fantasy VII")

    body = _get_roms(client, access_token, **params)

    assert body["char_index"] == expected


def _put_props(
    client: TestClient,
    access_token: str,
    rom_id: int,
    body: dict[str, Any] | None = None,
    **params: Any,
) -> None:
    response = client.put(
        f"/api/roms/{rom_id}/props",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
        json=body or {},
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.fixture
def played_rom(rom: Rom, admin_user: User) -> Rom:
    """The shared rom with an old `last_played`, so a later play must reorder past it."""
    rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
    assert rom_user is not None
    db_rom_handler.update_rom_user(
        rom_user.id, {"last_played": datetime(2020, 1, 1, tzinfo=timezone.utc)}
    )
    return rom


def _ingest_play_session(client: TestClient, access_token: str, rom_id: int) -> None:
    end = datetime.now(timezone.utc).replace(microsecond=0)
    response = client.post(
        "/api/play-sessions",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "sessions": [
                {
                    "rom_id": rom_id,
                    "start_time": (end - timedelta(minutes=30)).isoformat(),
                    "end_time": end.isoformat(),
                    "duration_ms": 30 * 60 * 1000,
                }
            ]
        },
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.parametrize("trigger", ["props", "play_session"])
def test_last_played_write_refreshes_the_sorted_index(
    client: TestClient,
    access_token: str,
    played_rom: Rom,
    second_rom: Rom,
    trigger: str,
):
    """Both `last_played` writers reorder the next sorted index."""
    first = _get_roms(client, access_token, order_by="last_played", order_dir="desc")
    assert first["rom_id_index"] == [played_rom.id, second_rom.id]

    if trigger == "props":
        _put_props(client, access_token, second_rom.id, update_last_played=True)
    else:
        _ingest_play_session(client, access_token, second_rom.id)

    second = _get_roms(client, access_token, order_by="last_played", order_dir="desc")
    assert second["rom_id_index"] == [second_rom.id, played_rom.id]


def test_main_sibling_write_refreshes_grouped_entry(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """Grouped sets pick the user's main sibling, so that write refreshes
    the grouped index even under the default name sort."""
    _seed_rom_id_index(_unscoped_key(admin_user.id, group=True), [424242])

    first = _get_roms(client, access_token, group_by_meta_id=True)
    assert first["rom_id_index"] == [424242]

    _put_props(client, access_token, rom.id, body={"is_main_sibling": True})

    second = _get_roms(client, access_token, group_by_meta_id=True)
    assert second["rom_id_index"] == [rom.id]


def test_non_sibling_write_keeps_the_grouped_entry(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """A play must not rotate the default grouped gallery's whole-library
    index; only main-sibling picks move a name-sorted grouped set."""
    _seed_rom_id_index(_unscoped_key(admin_user.id, group=True), [424242])

    _put_props(client, access_token, rom.id, update_last_played=True)

    body = _get_roms(client, access_token, group_by_meta_id=True)
    assert body["rom_id_index"] == [424242]


def test_rom_user_write_keeps_name_sorted_entry(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """A rating write must not rotate or delete the user's name-sorted entry."""
    redis_key = _seed_rom_id_index(_unscoped_key(admin_user.id), [424242])

    _put_props(client, access_token, rom.id, body={"rating": 8})

    body = _get_roms(client, access_token)
    assert body["rom_id_index"] == [424242]
    assert sync_cache.exists(redis_key)


def test_rom_user_write_leaves_other_users_sorted_entries_alone(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """One user's play rotates only their own key; another user's entry stays."""
    other_user_id = admin_user.id + 1
    writer_key = _unscoped_key(admin_user.id, "last_played", "desc")
    other_key = _unscoped_key(other_user_id, "last_played", "desc")
    other_redis_key = _seed_rom_id_index(other_key, [424242])

    _put_props(client, access_token, rom.id, update_last_played=True)

    assert _unscoped_key(other_user_id, "last_played", "desc") == other_key
    assert sync_cache.exists(other_redis_key)
    assert _unscoped_key(admin_user.id, "last_played", "desc") != writer_key


def test_hidden_write_still_bumps_the_global_version(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """`hidden` keeps its global invalidation on top of the per-user bump."""
    old_version = _filter_values_cache_version()
    redis_key = _seed_rom_id_index(_unscoped_key(admin_user.id), [424242])

    _put_props(client, access_token, rom.id, body={"hidden": True})

    assert int(_filter_values_cache_version()) == int(old_version) + 1
    assert not sync_cache.exists(redis_key)


def _page_ids(body: dict[str, Any]) -> list[int]:
    return [item["id"] for item in body["items"]]


GROUPED_PAGE = {"group_by_meta_id": True, "with_rom_id_index": False}


def test_grouped_page_slices_the_cached_unscoped_index(
    client: TestClient, access_token: str, admin_user: User, rom: Rom, second_rom: Rom
):
    """A grouped page without the index follows the cached id list."""
    _seed_rom_id_index(
        _unscoped_key(admin_user.id, group=True), [second_rom.id, rom.id]
    )

    body = _get_roms(client, access_token, **GROUPED_PAGE, with_total=True)

    assert _page_ids(body) == [second_rom.id, rom.id]
    assert body["total"] == 2
    assert body["rom_id_index"] == []

    body = _get_roms(client, access_token, **GROUPED_PAGE, limit=1, offset=1)
    assert _page_ids(body) == [rom.id]


def test_grouped_page_miss_stays_live_and_writes_nothing(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """Only the index request builds the cached list; a page miss runs live."""
    version = _filter_values_cache_version()
    redis_key = _rom_id_index_redis_key(
        _unscoped_key(admin_user.id, group=True), version
    )

    body = _get_roms(client, access_token, **GROUPED_PAGE, with_total=True)

    assert _page_ids(body) == [rom.id]
    assert body["total"] == 1
    assert not sync_cache.exists(redis_key)

    _get_roms(client, access_token, group_by_meta_id=True)
    assert [int(i) for i in sync_cache.lrange(redis_key, 0, -1)] == [rom.id]


def test_grouped_platform_index_shares_the_page_key(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    rom: Rom,
    second_rom: Rom,
):
    """The index request, its char index and the pages read one cached key."""
    page_key = _platform_key(admin_user.id, platform.id)
    _seed_rom_id_index(page_key, [second_rom.id, rom.id])
    version = _filter_values_cache_version()
    _store_versioned_cache(
        _char_index_redis_key(page_key, version), version, [["Z", 41]]
    )

    body = _get_roms(
        client, access_token, group_by_meta_id=True, platform_ids=platform.id
    )

    assert body["rom_id_index"] == [second_rom.id, rom.id]
    assert body["total"] == 2
    assert body["char_index"] == {"Z": 41}

    body = _get_roms(client, access_token, **GROUPED_PAGE, platform_ids=platform.id)
    assert _page_ids(body) == [second_rom.id, rom.id]


def test_grouped_platform_page_with_another_scope_stays_live(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    rom: Rom,
):
    """A search on top of the platforms narrows the set past the cached list."""
    page_key = _platform_key(admin_user.id, platform.id)
    _seed_rom_id_index(page_key, [424242])

    body = _get_roms(
        client,
        access_token,
        **GROUPED_PAGE,
        platform_ids=platform.id,
        search_term="test_rom",
    )

    assert _page_ids(body) == [rom.id]


def test_grouped_excluded_platform_page_skips_its_platform_key(
    client: TestClient,
    access_token: str,
    admin_user: User,
    platform: Platform,
    other_platform: Platform,
    rom: Rom,
):
    """Excluding one platform must not read that platform's cached list."""
    _seed_rom_id_index(_platform_key(admin_user.id, other_platform.id), [424242])

    body = _get_roms(
        client,
        access_token,
        **GROUPED_PAGE,
        platform_ids=other_platform.id,
        platforms_logic="none",
    )

    assert _page_ids(body) == [rom.id]


@pytest.mark.parametrize("platform_count", [2, 0])
def test_grouped_index_skips_unbounded_platform_keys(
    client: TestClient,
    access_token: str,
    platform: Platform,
    other_platform: Platform,
    rom: Rom,
    platform_count: int,
):
    """Multi-platform sets and empty lists (e.g. an unknown id) are not cached."""
    platform_ids = [platform.id, other_platform.id] if platform_count else [999999]
    version = _filter_values_cache_version()

    _get_roms(client, access_token, group_by_meta_id=True, platform_ids=platform_ids)

    cached_keys = sync_cache.smembers(_filter_values_cache_keys_key(version))
    assert not [key for key in cached_keys if "rom_id_list" in as_text(key)]


def test_platform_delete_bumps_the_global_version(
    client: TestClient, access_token: str, admin_user: User, platform: Platform
):
    """Grouped pages slice the cached list, so deleting a platform's roms drops it."""
    redis_key = _seed_rom_id_index(_unscoped_key(admin_user.id, group=True), [424242])
    old_version = _filter_values_cache_version()

    response = client.delete(
        f"/api/platforms/{platform.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == status.HTTP_200_OK

    assert int(_filter_values_cache_version()) == int(old_version) + 1
    assert not sync_cache.exists(redis_key)


def test_grouped_page_with_a_row_filter_stays_live(
    client: TestClient, access_token: str, admin_user: User, missing_rom: Rom
):
    """A row filter narrows the set, so neither cached list may answer it."""
    _seed_rom_id_index(_unscoped_key(admin_user.id, group=True), [424242])
    platform_key = _platform_key(admin_user.id, missing_rom.platform_id)
    _seed_rom_id_index(platform_key, [424242])

    body = _get_roms(client, access_token, **GROUPED_PAGE, missing=True)
    assert _page_ids(body) == [missing_rom.id]

    body = _get_roms(
        client,
        access_token,
        **GROUPED_PAGE,
        missing=True,
        platform_ids=missing_rom.platform_id,
    )
    assert _page_ids(body) == [missing_rom.id]


def test_ungrouped_page_does_not_read_the_cached_index(
    client: TestClient, access_token: str, admin_user: User, rom: Rom
):
    """Without grouping a page is a plain indexed query and stays live."""
    _seed_rom_id_index(_unscoped_key(admin_user.id), [424242])

    body = _get_roms(client, access_token, with_rom_id_index=False)

    assert _page_ids(body) == [rom.id]
