"""Unit tests for the Redis-backed, versioned filter/char-index cache.

`with_char_index` and the id index memoise their (expensive) results
in Redis under a key that embeds a global version number. Bumping that version
(via `invalidate_filter_values_cache`) is what makes every previously-cached
entry stale at once, and the per-version "keys set" is what lets the bump
actually delete the old entries instead of leaking them until TTL.

These tests pin down that machinery:
  1. storing a value also registers its key in the version set,
  2. a cache hit returns the exact same shape as the cache miss that filled it,
  3. `invalidate_filter_values_cache()` deletes the prior version's keys,
  4. a rom_user write bumps only the writing user's per-user version.
"""

import json
from collections.abc import Iterable
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from tests.conftest import session as session_factory

from handler.database import db_platform_handler, db_rom_handler
from handler.database.roms_handler import (
    ROM_FILTERS_CACHE_VERSION_KEY,
    _char_index_redis_key,
    _filter_values_cache_keys_key,
    _filter_values_cache_version,
    _rom_id_index_redis_key,
    _store_versioned_cache,
    _store_versioned_id_list,
    user_sibling_cache_version,
    user_sort_cache_version,
)
from handler.redis_handler import as_text, sync_cache
from models.rom import Rom
from models.user import User


@pytest.fixture(autouse=True)
def _flush_cache():
    """Start every test from an empty cache (version resets to "0").

    The autouse `clear_database` fixture bumps the version key on its way in;
    flushing afterwards keeps these tests independent of that counter.
    """
    sync_cache.flushall()
    yield
    sync_cache.flushall()


def _decode_members(raw_members: Iterable[bytes | str]) -> set[str]:
    return {as_text(m) for m in raw_members}


def _set_rom_genres(rom_id: int, genres: list[str]) -> None:
    """Drive the `roms_metadata` view by writing the source `igdb_metadata`.

    `roms_metadata` is a DB view derived from `roms.igdb_metadata` (etc.), so
    metadata is seeded by writing that JSON column, not by inserting into the
    view.
    """
    with session_factory.begin() as s:
        rom: Rom | None = s.get(Rom, rom_id)
        assert rom is not None
        metadata = dict(rom.igdb_metadata or {})
        metadata["genres"] = genres
        rom.igdb_metadata = metadata


@pytest.fixture
def rom_with_metadata(rom: Rom) -> Rom:
    """Give the shared `rom` a genre so filter values are non-empty."""
    _set_rom_genres(rom.id, ["RPG"])
    return rom


class TestStoreVersionedCache:
    def test_stores_value_and_registers_key_in_version_set(self):
        version = _filter_values_cache_version()
        assert version == "0"

        redis_key = f"filter_values:probe:v{version}"
        result = {"genres": ["RPG"], "platforms": [1]}

        _store_versioned_cache(redis_key, version, result)

        # The value itself round-trips as JSON under the key.
        cached_result = sync_cache.get(redis_key)
        assert cached_result is not None
        assert json.loads(cached_result) == result

        # ...and the key is recorded in this version's keys-set so a later
        # invalidation can find and delete it.
        members = _decode_members(
            sync_cache.smembers(_filter_values_cache_keys_key(version))
        )
        assert redis_key in members

    def test_skips_write_when_version_advanced_mid_flight(self):
        """If the version moved on while we were computing, don't write back.

        This guards the race where an invalidation lands between reading the
        version and storing the result: a stale entry must not resurrect under
        a key the next invalidation no longer knows about.
        """
        stale_version = _filter_values_cache_version()  # "0"
        sync_cache.set(ROM_FILTERS_CACHE_VERSION_KEY, "9")

        redis_key = f"filter_values:probe:v{stale_version}"
        _store_versioned_cache(redis_key, stale_version, {"genres": []})

        assert sync_cache.get(redis_key) is None
        assert (
            sync_cache.smembers(_filter_values_cache_keys_key(stale_version)) == set()
        )


class TestCacheHitMatchesMiss:
    def test_with_filter_values_reads_the_database_every_time(
        self, rom_with_metadata: Rom
    ):
        query = select(Rom)

        first = db_rom_handler.with_filter_values(query=query)
        assert first["genres"] == ["RPG"]

        _set_rom_genres(rom_with_metadata.id, ["RPG", "Action"])

        assert db_rom_handler.with_filter_values(query=query)["genres"] == [
            "Action",
            "RPG",
        ]
        assert sync_cache.keys("filter_values:*") == []

    def test_with_char_index_hit_matches_miss(self, rom: Rom):
        query = select(Rom)
        cache_key = "all:test-charindex"

        miss = db_rom_handler.with_char_index(
            query=query, order_by_attr=Rom.name, cache_key=cache_key
        )

        version = _filter_values_cache_version()
        redis_key = _char_index_redis_key(cache_key, version)
        assert sync_cache.get(redis_key) is not None
        # "test_rom" -> first letter "t" at position 0.
        assert dict(miss) == {"t": 0}

        # Add a ROM under a new letter; a cache hit must ignore it.
        with session_factory.begin() as s:
            s.add(
                Rom(
                    platform_id=rom.platform_id,
                    name="Another",
                    slug="another-slug",
                    fs_name="another.zip",
                    fs_name_no_tags="another",
                    fs_name_no_ext="another",
                    fs_extension="zip",
                    fs_path=rom.fs_path,
                )
            )

        hit = db_rom_handler.with_char_index(
            query=query, order_by_attr=Rom.name, cache_key=cache_key
        )

        # Same consumed shape as the miss (the endpoint folds this into a dict).
        assert dict(hit) == dict(miss) == {"t": 0}

    def test_get_rom_id_index_hit_matches_miss(self, rom: Rom):
        query = select(Rom)
        cache_key = "all:test-idindex"

        miss = db_rom_handler.get_rom_id_index(query=query, cache_key=cache_key)

        version = _filter_values_cache_version()
        redis_key = _rom_id_index_redis_key(cache_key, version)
        assert sync_cache.exists(redis_key)
        assert miss == [rom.id]

        # Add a ROM; a cache hit must ignore it until the version bumps.
        with session_factory.begin() as s:
            s.add(
                Rom(
                    platform_id=rom.platform_id,
                    name="Another",
                    slug="another-slug-idx",
                    fs_name="another-idx.zip",
                    fs_name_no_tags="another-idx",
                    fs_name_no_ext="another-idx",
                    fs_extension="zip",
                    fs_path=rom.fs_path,
                )
            )

        hit = db_rom_handler.get_rom_id_index(query=query, cache_key=cache_key)
        assert hit == miss == [rom.id]

    def test_cached_rom_id_page_reads_a_window_without_writing(self, rom: Rom):
        cache_key = "all:test-idpage"

        assert db_rom_handler.get_cached_rom_id_page(cache_key, 0, 10) is None
        version = _filter_values_cache_version()
        assert not sync_cache.exists(_rom_id_index_redis_key(cache_key, version))

        _store_versioned_id_list(
            _rom_id_index_redis_key(cache_key, version), version, [5, 4, 3, 2]
        )

        assert db_rom_handler.get_cached_rom_id_page(cache_key, 1, 2) == ([4, 3], 4)
        assert db_rom_handler.get_cached_rom_id_page(cache_key, 9, 2) == ([], 4)

    def test_an_empty_id_index_is_not_cached(self):
        cache_key = "all:test-idempty"

        ids = db_rom_handler.get_rom_id_index(
            query=select(Rom).where(Rom.id == -1), cache_key=cache_key
        )

        assert ids == []
        version = _filter_values_cache_version()
        assert not sync_cache.exists(_rom_id_index_redis_key(cache_key, version))

    @pytest.mark.parametrize("target", ["rom", "platform"])
    def test_a_delete_bumps_the_version_after_commit(self, rom: Rom, target: str):
        old_version = _filter_values_cache_version()

        if target == "rom":
            db_rom_handler.delete_rom(rom.id)
        else:
            db_platform_handler.delete_platform(rom.platform_id)

        assert int(_filter_values_cache_version()) == int(old_version) + 1


# The rom fixtures call add_rom_user, which itself bumps, so every
# assertion here is a delta from the version the setup left behind.
class TestRomUserCacheVersion:
    def test_update_rom_user_bumps_only_that_users_sort_version(
        self, rom: Rom, admin_user: User
    ):
        rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
        assert rom_user is not None
        before = int(user_sort_cache_version(admin_user.id))
        sibling_before = user_sibling_cache_version(admin_user.id)

        db_rom_handler.update_rom_user(
            rom_user.id, {"last_played": datetime(2020, 1, 1, tzinfo=timezone.utc)}
        )

        assert int(user_sort_cache_version(admin_user.id)) == before + 1
        # Another user, the sibling counter, and the global version stay put.
        assert user_sort_cache_version(admin_user.id + 1) == "0"
        assert user_sibling_cache_version(admin_user.id) == sibling_before
        assert _filter_values_cache_version() == "0"

    def test_main_sibling_write_bumps_the_sibling_version(
        self, rom: Rom, admin_user: User
    ):
        rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
        assert rom_user is not None
        before = int(user_sibling_cache_version(admin_user.id))

        db_rom_handler.update_rom_user(rom_user.id, {"is_main_sibling": True})

        assert int(user_sibling_cache_version(admin_user.id)) == before + 1

    def test_hidden_only_write_skips_the_sort_version(self, rom: Rom, admin_user: User):
        # `hidden` rotates every key through the global bump already.
        rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
        assert rom_user is not None
        before = user_sort_cache_version(admin_user.id)

        db_rom_handler.update_rom_user(rom_user.id, {"hidden": True})

        assert user_sort_cache_version(admin_user.id) == before

    def test_add_rom_user_bumps_the_sort_version(self, rom: Rom, admin_user: User):
        # The `rom` fixture already pairs itself with admin_user, so a fresh
        # row needs a rom of its own.
        with session_factory.begin() as s:
            bare_rom = Rom(
                platform_id=rom.platform_id,
                name="Bare",
                slug="bare-slug",
                fs_name="bare.zip",
                fs_name_no_tags="bare",
                fs_name_no_ext="bare",
                fs_extension="zip",
                fs_path=rom.fs_path,
            )
            s.add(bare_rom)
            s.flush()
            bare_rom_id = bare_rom.id
        before = int(user_sort_cache_version(admin_user.id))

        # A fresh row's zero defaults replace NULL sort keys.
        db_rom_handler.add_rom_user(rom_id=bare_rom_id, user_id=admin_user.id)

        assert int(user_sort_cache_version(admin_user.id)) == before + 1

    def test_missing_rom_user_does_not_bump(self, admin_user: User):
        before = user_sort_cache_version(admin_user.id)
        assert db_rom_handler.update_rom_user(424242, {"rating": 8}) is None
        assert user_sort_cache_version(admin_user.id) == before

    def test_reused_session_bumps_on_every_commit(self, rom: Rom, admin_user: User):
        rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
        assert rom_user is not None
        before = int(user_sort_cache_version(admin_user.id))

        with session_factory() as session:
            db_rom_handler.update_rom_user(rom_user.id, {"rating": 4}, session=session)
            session.commit()
            db_rom_handler.update_rom_user(rom_user.id, {"rating": 5}, session=session)
            session.commit()

        assert int(user_sort_cache_version(admin_user.id)) == before + 2

    def test_rolled_back_write_does_not_bump(self, rom: Rom, admin_user: User):
        rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
        assert rom_user is not None
        before = user_sort_cache_version(admin_user.id)

        with session_factory() as session:
            db_rom_handler.update_rom_user(rom_user.id, {"rating": 4}, session=session)
            session.rollback()
            # An empty commit after the rollback must not flush the
            # discarded bumps.
            session.commit()

        assert user_sort_cache_version(admin_user.id) == before

    def test_rolled_back_savepoint_keeps_earlier_bumps(
        self, rom: Rom, admin_user: User
    ):
        rom_user = db_rom_handler.get_rom_user(rom.id, admin_user.id)
        assert rom_user is not None
        before = int(user_sort_cache_version(admin_user.id))

        with session_factory.begin() as session:
            db_rom_handler.update_rom_user(rom_user.id, {"rating": 4}, session=session)
            # The row exists, so the insert's savepoint rolls back.
            db_rom_handler.add_rom_user(rom.id, admin_user.id, session=session)

        assert int(user_sort_cache_version(admin_user.id)) == before + 1


class TestInvalidateFilterValuesCache:
    def test_deletes_prior_version_keys_and_set(self, rom_with_metadata: Rom):
        query = select(Rom)

        # Populate the cache under the current version.
        db_rom_handler.with_char_index(
            query=query, order_by_attr=Rom.name, cache_key="all:charindex"
        )

        old_version = _filter_values_cache_version()
        old_keys_set = _filter_values_cache_keys_key(old_version)
        old_keys = _decode_members(sync_cache.smembers(old_keys_set))
        assert old_keys  # something was registered
        assert all(sync_cache.get(key) is not None for key in old_keys)

        db_rom_handler.invalidate_filter_values_cache()

        # Version advanced...
        new_version = _filter_values_cache_version()
        assert int(new_version) == int(old_version) + 1

        # ...the prior version's value keys are gone...
        assert all(sync_cache.get(key) is None for key in old_keys)
        # ...and so is the bookkeeping set itself.
        assert sync_cache.smembers(old_keys_set) == set()
