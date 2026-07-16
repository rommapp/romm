"""Unit tests for the Redis-backed, versioned gallery sidecar cache.

`with_char_index` and `get_rom_id_index` memoise their (expensive) results in
Redis under a key that embeds a global version number. Bumping that version
(via `invalidate_gallery_sidecar_cache`) is what makes every previously-cached
entry stale at once, and the per-version "keys set" is what lets the bump
actually delete the old entries instead of leaking them until TTL.

(Facet filter values are no longer cached: they read from the materialized
`roms_metadata` table and are cheap to compute, issue #3768.)

These tests pin down that machinery:
  1. storing a value also registers its key in the version set,
  2. a cache hit returns the exact same shape as the cache miss that filled it,
  3. `invalidate_gallery_sidecar_cache()` deletes the prior version's keys.
"""

import json
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Query
from tests.conftest import session as session_factory

from handler.database import db_rom_handler
from handler.database.roms_handler import (
    GALLERY_SIDECAR_CACHE_VERSION_KEY,
    _gallery_sidecar_cache_keys_key,
    _gallery_sidecar_cache_version,
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


class TestStoreVersionedCache:
    def test_stores_value_and_registers_key_in_version_set(self):
        version = _gallery_sidecar_cache_version()
        assert version == "0"

        redis_key = f"gallery_sidecar:probe:v{version}"
        result = [["t", 0]]

        _store_versioned_cache(redis_key, version, result)

        # The value itself round-trips as JSON under the key.
        cached_result = sync_cache.get(redis_key)
        assert cached_result is not None
        assert json.loads(cached_result) == result

        # ...and the key is recorded in this version's keys-set so a later
        # invalidation can find and delete it.
        members = _decode_members(
            sync_cache.smembers(_gallery_sidecar_cache_keys_key(version))
        )
        assert redis_key in members

    def test_skips_write_when_version_advanced_mid_flight(self):
        """If the version moved on while we were computing, don't write back.

        This guards the race where an invalidation lands between reading the
        version and storing the result: a stale entry must not resurrect under
        a key the next invalidation no longer knows about.
        """
        stale_version = _gallery_sidecar_cache_version()  # "0"
        sync_cache.set(GALLERY_SIDECAR_CACHE_VERSION_KEY, "9")

        redis_key = f"gallery_sidecar:probe:v{stale_version}"
        _store_versioned_cache(redis_key, stale_version, [])

        assert sync_cache.get(redis_key) is None
        assert (
            sync_cache.smembers(_gallery_sidecar_cache_keys_key(stale_version)) == set()
        )


class TestCacheHitMatchesMiss:
    def test_with_char_index_hit_matches_miss(self, rom: Rom):
        query = cast(Query[Rom], select(Rom))
        cache_key = "all:test-charindex"

        miss = db_rom_handler.with_char_index(
            query=query, order_by_attr=Rom.name, cache_key=cache_key
        )

        version = _gallery_sidecar_cache_version()
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

    def test_get_rom_id_index_hit_matches_miss(self, rom: Rom):
        query = cast(Query[Rom], select(Rom))
        cache_key = "all:test-idindex"

        miss = db_rom_handler.get_rom_id_index(query=query, cache_key=cache_key)

        version = _gallery_sidecar_cache_version()
        redis_key = f"rom_id_index:{cache_key}:v{version}"
        assert sync_cache.get(redis_key) is not None
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


class TestInvalidateGallerySidecarCache:
    def test_deletes_prior_version_keys_and_set(self, rom: Rom):
        query = cast(Query[Rom], select(Rom))

        # Populate both sidecar caches under the current version.
        db_rom_handler.with_char_index(
            query=query, order_by_attr=Rom.name, cache_key="all:charindex"
        )
        db_rom_handler.get_rom_id_index(query=query, cache_key="all:idindex")

        old_version = _gallery_sidecar_cache_version()
        old_keys_set = _gallery_sidecar_cache_keys_key(old_version)
        old_keys = _decode_members(sync_cache.smembers(old_keys_set))
        assert old_keys  # something was registered
        assert all(sync_cache.get(key) is not None for key in old_keys)

        db_rom_handler.invalidate_gallery_sidecar_cache()

        # Version advanced...
        new_version = _gallery_sidecar_cache_version()
        assert int(new_version) == int(old_version) + 1

        # ...the prior version's value keys are gone...
        assert all(sync_cache.get(key) is None for key in old_keys)
        # ...and so is the bookkeeping set itself.
        assert sync_cache.smembers(old_keys_set) == set()

    def test_recomputes_under_new_version_after_invalidation(self, rom: Rom):
        query = cast(Query[Rom], select(Rom))
        cache_key = "all:idindex"

        db_rom_handler.get_rom_id_index(query=query, cache_key=cache_key)

        # Add a ROM, then invalidate: the next call must reflect the new row
        # because the old cached entry no longer resolves under the new version.
        with session_factory.begin() as s:
            s.add(
                Rom(
                    platform_id=rom.platform_id,
                    name="Fresh",
                    slug="fresh-slug",
                    fs_name="fresh.zip",
                    fs_name_no_tags="fresh",
                    fs_name_no_ext="fresh",
                    fs_extension="zip",
                    fs_path=rom.fs_path,
                )
            )

        db_rom_handler.invalidate_gallery_sidecar_cache()

        fresh = db_rom_handler.get_rom_id_index(query=query, cache_key=cache_key)
        assert len(fresh) == 2

        new_version = _gallery_sidecar_cache_version()
        redis_key = f"rom_id_index:{cache_key}:v{new_version}"
        assert sync_cache.get(redis_key) is not None
