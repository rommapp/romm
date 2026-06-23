"""Unit tests for the Redis-backed, versioned filter/char-index cache.

`with_filter_values` and `with_char_index` memoise their (expensive) results
in Redis under a key that embeds a global version number. Bumping that version
(via `invalidate_filter_values_cache`) is what makes every previously-cached
entry stale at once, and the per-version "keys set" is what lets the bump
actually delete the old entries instead of leaking them until TTL.

These tests pin down that machinery:
  1. storing a value also registers its key in the version set,
  2. a cache hit returns the exact same shape as the cache miss that filled it,
  3. `invalidate_filter_values_cache()` deletes the prior version's keys.
"""

import json
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Query
from tests.conftest import session as session_factory

from handler.database import db_rom_handler
from handler.database.roms_handler import (
    ROM_FILTERS_CACHE_VERSION_KEY,
    _filter_values_cache_keys_key,
    _filter_values_cache_version,
    _store_versioned_cache,
)
from handler.redis_handler import sync_cache
from models.rom import Rom


@pytest.fixture(autouse=True)
def _flush_cache():
    """Start every test from an empty cache (version resets to "0").

    The autouse `clear_database` fixture bumps the version key on its way in;
    flushing afterwards keeps these tests independent of that counter.
    """
    sync_cache.flushall()
    yield
    sync_cache.flushall()


def _decode_members(raw_members: set) -> set[str]:
    return {m.decode() if isinstance(m, bytes) else m for m in raw_members}


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
    def test_with_filter_values_hit_matches_miss(self, rom_with_metadata: Rom):
        query = cast(Query[Rom], select(Rom))
        cache_key = "all:test-filters"

        miss = db_rom_handler.with_filter_values(query=query, cache_key=cache_key)

        # The miss must have populated the cache under the current version.
        version = _filter_values_cache_version()
        redis_key = f"filter_values:{cache_key}:v{version}"
        assert sync_cache.get(redis_key) is not None
        assert miss["genres"] == ["RPG"]

        # Mutating the DB after the miss must NOT change a subsequent hit:
        # proves the second call is served from cache, byte-for-byte identical.
        _set_rom_genres(rom_with_metadata.id, ["RPG", "Action"])

        hit = db_rom_handler.with_filter_values(query=query, cache_key=cache_key)

        assert hit == miss
        assert hit.keys() == miss.keys()

    def test_with_filter_values_without_cache_key_does_not_cache(
        self, rom_with_metadata: Rom
    ):
        query = cast(Query[Rom], select(Rom))
        result = db_rom_handler.with_filter_values(query=query)

        # Nothing written, and a sane shape is still returned.
        assert sync_cache.keys("filter_values:*") == []
        assert result["genres"] == ["RPG"]

    def test_with_char_index_hit_matches_miss(self, rom: Rom):
        query = cast(Query[Rom], select(Rom))
        cache_key = "all:test-charindex"

        miss = db_rom_handler.with_char_index(
            query=query, order_by_attr=Rom.name, cache_key=cache_key
        )

        version = _filter_values_cache_version()
        redis_key = f"char_index:{cache_key}:v{version}"
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


class TestInvalidateFilterValuesCache:
    def test_deletes_prior_version_keys_and_set(self, rom_with_metadata: Rom):
        query = cast(Query[Rom], select(Rom))

        # Populate both caches under the current version.
        db_rom_handler.with_filter_values(query=query, cache_key="all:filters")
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

    def test_recomputes_under_new_version_after_invalidation(
        self, rom_with_metadata: Rom
    ):
        query = cast(Query[Rom], select(Rom))
        cache_key = "all:filters"

        db_rom_handler.with_filter_values(query=query, cache_key=cache_key)

        # Change the data, then invalidate: the next call must reflect the change
        # because the old cached entry no longer resolves under the new version.
        _set_rom_genres(rom_with_metadata.id, ["RPG", "Action"])

        db_rom_handler.invalidate_filter_values_cache()

        fresh = db_rom_handler.with_filter_values(query=query, cache_key=cache_key)
        assert fresh["genres"] == ["Action", "RPG"]

        new_version = _filter_values_cache_version()
        assert sync_cache.get(f"filter_values:{cache_key}:v{new_version}") is not None
