import os
import time
from zipfile import ZipFile

import pytest

from utils.zip_cache import (
    BULK_CACHE_MAX_ROMS,
    BULK_NAMESPACE_PREFIX,
    CACHE_KEY_LENGTH,
    DEFAULT_TTL_HOURS,
    LARGE_ZIP_THRESHOLD_BYTES,
    LARGE_ZIP_TTL_HOURS,
    SECONDS_PER_HOUR,
    ZipFileEntry,
    build_cached_zip,
    cleanup_stale_zips,
    get_bulk_namespace,
    get_cache_key,
    get_cached_zip,
    get_ttl_hours,
    get_zip_redirect_path,
    resolve_cached_zip,
)


def _entry(
    name: str = "game.bin", size: int = 1024, epoch: float = 1000.0
) -> ZipFileEntry:
    return ZipFileEntry(
        download_name=name,
        full_path=f"roms/nes/{name}",
        file_size_bytes=size,
        updated_at_epoch=epoch,
    )


class TestGetCacheKey:
    def test_deterministic(self):
        entries = [_entry("a.bin", 100), _entry("b.bin", 200)]
        key1 = get_cache_key("1", entries, False)
        key2 = get_cache_key("1", entries, False)
        assert key1 == key2

    def test_different_namespaces(self):
        entries = [_entry()]
        assert get_cache_key("1", entries, False) != get_cache_key("2", entries, False)

    def test_different_hidden_folder(self):
        entries = [_entry()]
        assert get_cache_key("1", entries, False) != get_cache_key("1", entries, True)

    def test_different_files(self):
        e1 = [_entry("a.bin")]
        e2 = [_entry("b.bin")]
        assert get_cache_key("1", e1, False) != get_cache_key("1", e2, False)

    def test_different_updated_at(self):
        e1 = [_entry(epoch=1000.0)]
        e2 = [_entry(epoch=2000.0)]
        assert get_cache_key("1", e1, False) != get_cache_key("1", e2, False)

    def test_order_independent(self):
        entries_a = [_entry("a.bin", 100), _entry("b.bin", 200)]
        entries_b = [_entry("b.bin", 200), _entry("a.bin", 100)]
        assert get_cache_key("1", entries_a, False) == get_cache_key(
            "1", entries_b, False
        )

    def test_returns_hex_string(self):
        key = get_cache_key("1", [_entry()], False)
        assert len(key) == CACHE_KEY_LENGTH
        int(key, 16)

    def test_file_change_invalidates_cache(self):
        entries_v1 = [
            _entry("disc1.chd", 500, epoch=1000.0),
            _entry("disc2.chd", 600, epoch=1000.0),
        ]
        entries_v2 = [
            _entry("disc1.chd", 500, epoch=1000.0),
            _entry("disc2.chd", 600, epoch=2000.0),
        ]
        assert get_cache_key("1", entries_v1, False) != get_cache_key(
            "1", entries_v2, False
        )

    def test_file_size_change_invalidates_cache(self):
        e1 = [_entry("game.bin", size=1000, epoch=1000.0)]
        e2 = [_entry("game.bin", size=2000, epoch=1000.0)]
        assert get_cache_key("1", e1, False) != get_cache_key("1", e2, False)

    def test_bulk_namespace(self):
        entries = [_entry()]
        key_single = get_cache_key("42", entries)
        key_bulk = get_cache_key("bulk-abc123", entries)
        assert key_single != key_bulk

    def test_empty_entries(self):
        key = get_cache_key("1", [], False)
        assert len(key) == CACHE_KEY_LENGTH
        int(key, 16)


class TestGetBulkNamespace:
    def test_deterministic(self):
        assert get_bulk_namespace([1, 2, 3]) == get_bulk_namespace([1, 2, 3])

    def test_order_independent(self):
        assert get_bulk_namespace([3, 1, 2]) == get_bulk_namespace([1, 2, 3])

    def test_starts_with_prefix(self):
        ns = get_bulk_namespace([1, 2])
        assert ns.startswith(f"{BULK_NAMESPACE_PREFIX}-")

    def test_short_enough_for_filesystem(self):
        ids = list(range(1, 101))
        ns = get_bulk_namespace(ids)
        assert len(ns) < 255

    def test_different_ids_produce_different_namespace(self):
        assert get_bulk_namespace([1, 2]) != get_bulk_namespace([1, 3])


class TestGetCachedZip:
    def test_returns_none_when_missing(self, tmp_path, mocker):
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert get_cached_zip("1", "abc123") is None

    def test_returns_path_when_exists(self, tmp_path, mocker):
        ns_dir = tmp_path / "1"
        ns_dir.mkdir()
        (ns_dir / "abc123.zip").write_bytes(b"fake")
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        result = get_cached_zip("1", "abc123")
        assert result is not None
        assert result.name == "abc123.zip"

    def test_old_key_not_returned_for_new_key(self, tmp_path, mocker):
        ns_dir = tmp_path / "1"
        ns_dir.mkdir()
        (ns_dir / "oldkey.zip").write_bytes(b"old content")
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert get_cached_zip("1", "oldkey") is not None
        assert get_cached_zip("1", "newkey") is None


class TestBuildCachedZip:
    @pytest.fixture
    def source_files(self, tmp_path):
        lib = tmp_path / "library"
        rom_dir = lib / "roms" / "nes"
        rom_dir.mkdir(parents=True)
        (rom_dir / "disc1.chd").write_bytes(b"disc1data")
        (rom_dir / "disc2.chd").write_bytes(b"disc2data")
        return lib

    def test_builds_valid_zip(self, tmp_path, source_files, mocker):
        cache_dir = tmp_path / "cache"
        entries = [
            ZipFileEntry("disc1.chd", "roms/nes/disc1.chd", 9, 1000.0),
            ZipFileEntry("disc2.chd", "roms/nes/disc2.chd", 9, 1000.0),
        ]
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(cache_dir))
        mocker.patch("utils.zip_cache.LIBRARY_BASE_PATH", str(source_files))
        result = build_cached_zip(
            namespace="42",
            entries=entries,
            m3u_content=None,
            m3u_filename=None,
            cache_key="testkey",
        )

        assert result.exists()
        with ZipFile(result) as zf:
            names = zf.namelist()
            assert "disc1.chd" in names
            assert "disc2.chd" in names
            assert zf.read("disc1.chd") == b"disc1data"

    def test_includes_m3u(self, tmp_path, source_files, mocker):
        cache_dir = tmp_path / "cache"
        entries = [ZipFileEntry("disc1.chd", "roms/nes/disc1.chd", 9, 1000.0)]
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(cache_dir))
        mocker.patch("utils.zip_cache.LIBRARY_BASE_PATH", str(source_files))
        result = build_cached_zip(
            namespace="42",
            entries=entries,
            m3u_content=b"disc1.chd\ndisc2.chd",
            m3u_filename="game.m3u",
            cache_key="testkey2",
        )

        with ZipFile(result) as zf:
            assert "game.m3u" in zf.namelist()
            assert zf.read("game.m3u") == b"disc1.chd\ndisc2.chd"

    def test_skips_build_if_exists(self, tmp_path, mocker):
        cache_dir = tmp_path / "cache" / "42"
        cache_dir.mkdir(parents=True)
        existing = cache_dir / "existing.zip"
        existing.write_bytes(b"already here")

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path / "cache"))
        result = build_cached_zip(
            namespace="42",
            entries=[ZipFileEntry("disc1.chd", "roms/nes/disc1.chd", 9, 1000.0)],
            m3u_content=None,
            m3u_filename=None,
            cache_key="existing",
        )
        assert result.read_bytes() == b"already here"

    def test_cleans_up_temp_on_error(self, tmp_path, source_files, mocker):
        cache_dir = tmp_path / "cache"
        entries = [ZipFileEntry("missing.bin", "roms/nes/missing.bin", 100, 1000.0)]
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(cache_dir))
        mocker.patch("utils.zip_cache.LIBRARY_BASE_PATH", str(source_files))

        with pytest.raises(FileNotFoundError):
            build_cached_zip(
                namespace="42",
                entries=entries,
                m3u_content=None,
                m3u_filename=None,
                cache_key="failkey",
            )

        rom_cache = cache_dir / "42"
        if rom_cache.exists():
            assert not list(rom_cache.glob("*.tmp"))

    def test_new_key_builds_alongside_old(self, tmp_path, source_files, mocker):
        cache_dir = tmp_path / "cache"
        rom_cache = cache_dir / "42"
        rom_cache.mkdir(parents=True)
        old_zip = rom_cache / "oldkey.zip"
        old_zip.write_bytes(b"old zip content")

        entries = [ZipFileEntry("disc1.chd", "roms/nes/disc1.chd", 9, 2000.0)]
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(cache_dir))
        mocker.patch("utils.zip_cache.LIBRARY_BASE_PATH", str(source_files))
        build_cached_zip(
            namespace="42",
            entries=entries,
            m3u_content=None,
            m3u_filename=None,
            cache_key="newkey",
        )

        assert old_zip.exists(), "Old cache must not be deleted during build"
        assert (rom_cache / "newkey.zip").exists()


class TestGetZipRedirectPath:
    def test_single_rom_path(self):
        assert str(get_zip_redirect_path("42", "abc123")) == "/cache/zips/42/abc123.zip"

    def test_bulk_path(self):
        ns = get_bulk_namespace([1, 2, 3])
        path = str(get_zip_redirect_path(ns, "abc123"))
        assert path.startswith("/cache/zips/bulk-")
        assert path.endswith("/abc123.zip")


class TestResolveCachedZip:
    async def test_returns_none_for_empty_entries(self):
        result = await resolve_cached_zip("42", [], log_label="test")
        assert result is None

    async def test_returns_redirect_on_cache_hit(self, tmp_path, mocker):
        entries = [_entry()]
        cache_key = get_cache_key("42", entries)
        ns_dir = tmp_path / "42"
        ns_dir.mkdir()
        (ns_dir / f"{cache_key}.zip").write_bytes(b"cached")
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))

        build = mocker.patch("utils.zip_cache.build_cached_zip")
        result = await resolve_cached_zip("42", entries, log_label="test")

        assert str(result) == f"/cache/zips/42/{cache_key}.zip"
        build.assert_not_called()

    async def test_builds_and_returns_redirect_on_miss(self, tmp_path, mocker):
        entries = [_entry()]
        cache_key = get_cache_key("42", entries)
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        build = mocker.patch("utils.zip_cache.build_cached_zip")

        result = await resolve_cached_zip("42", entries, log_label="test")

        assert str(result) == f"/cache/zips/42/{cache_key}.zip"
        build.assert_called_once()

    async def test_returns_none_when_build_fails(self, tmp_path, mocker):
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        mocker.patch(
            "utils.zip_cache.build_cached_zip", side_effect=OSError("disk full")
        )
        result = await resolve_cached_zip("42", [_entry()], log_label="test")
        assert result is None


class TestGetTtlHours:
    def test_small_zip_gets_default_ttl(self):
        assert get_ttl_hours(1024) == DEFAULT_TTL_HOURS

    def test_large_zip_gets_reduced_ttl(self):
        assert get_ttl_hours(LARGE_ZIP_THRESHOLD_BYTES + 1) == LARGE_ZIP_TTL_HOURS


class TestCleanupStaleZips:
    def test_deletes_old_files(self, tmp_path, mocker):
        ns_dir = tmp_path / "1"
        ns_dir.mkdir()
        old_zip = ns_dir / "old.zip"
        old_zip.write_bytes(b"stale")
        old_time = time.time() - (DEFAULT_TTL_HOURS + 1) * SECONDS_PER_HOUR
        os.utime(old_zip, (old_time, old_time))

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert cleanup_stale_zips() == 1
        assert not old_zip.exists()

    def test_keeps_recent_files(self, tmp_path, mocker):
        ns_dir = tmp_path / "1"
        ns_dir.mkdir()
        recent = ns_dir / "recent.zip"
        recent.write_bytes(b"fresh")

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert cleanup_stale_zips() == 0
        assert recent.exists()

    def test_removes_empty_directories(self, tmp_path, mocker):
        ns_dir = tmp_path / "1"
        ns_dir.mkdir()
        old_zip = ns_dir / "old.zip"
        old_zip.write_bytes(b"stale")
        old_time = time.time() - (DEFAULT_TTL_HOURS + 1) * SECONDS_PER_HOUR
        os.utime(old_zip, (old_time, old_time))

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        cleanup_stale_zips()
        assert not ns_dir.exists()

    def test_handles_missing_cache_dir(self, tmp_path, mocker):
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path / "nonexistent"))
        assert cleanup_stale_zips() == 0

    def test_keeps_dir_with_remaining_files(self, tmp_path, mocker):
        ns_dir = tmp_path / "1"
        ns_dir.mkdir()

        old_zip = ns_dir / "old.zip"
        old_zip.write_bytes(b"stale")
        old_time = time.time() - (DEFAULT_TTL_HOURS + 1) * SECONDS_PER_HOUR
        os.utime(old_zip, (old_time, old_time))

        fresh_zip = ns_dir / "fresh.zip"
        fresh_zip.write_bytes(b"current")

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert cleanup_stale_zips() == 1
        assert not old_zip.exists()
        assert fresh_zip.exists()
        assert ns_dir.exists()

    def test_large_files_use_shorter_ttl(self, tmp_path, mocker):
        ns_dir = tmp_path / "1"
        ns_dir.mkdir()
        large_zip = ns_dir / "large.zip"
        # Use truncate for sparse file instead of allocating 8GB+
        with open(large_zip, "wb") as f:
            f.truncate(LARGE_ZIP_THRESHOLD_BYTES + 1)
        age = (LARGE_ZIP_TTL_HOURS + 1) * SECONDS_PER_HOUR
        old_time = time.time() - age
        os.utime(large_zip, (old_time, old_time))

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert cleanup_stale_zips() == 1


class TestZipFileEntryFromRomFile:
    def test_maps_fields(self, mocker):
        rom_file = mocker.MagicMock()
        rom_file.file_name_for_download.return_value = ".hidden/game.chd"
        rom_file.full_path = "roms/nes/game.chd"
        rom_file.file_size_bytes = 2048
        rom_file.updated_at.timestamp.return_value = 1234.5

        entry = ZipFileEntry.from_rom_file(rom_file, hidden_folder=True)

        rom_file.file_name_for_download.assert_called_once_with(True)
        assert entry == ZipFileEntry(
            ".hidden/game.chd", "roms/nes/game.chd", 2048, 1234.5
        )


class TestEnsureZipfileWritable:
    def test_writestr_works_after_inflate64_patch(self, tmp_path, mocker):
        # Simulates the zipfile_inflate64 patch: a wrapper that drops the
        # compresslevel argument, which breaks ZipFile.write() on CPython 3.13.
        import zipfile

        original = zipfile._get_compressor  # type: ignore[attr-defined]

        def one_arg_wrapper(compress_type):
            return original(compress_type)

        mocker.patch.object(zipfile, "_get_compressor", one_arg_wrapper)

        lib = tmp_path / "library"
        (lib / "roms").mkdir(parents=True)
        (lib / "roms" / "a.bin").write_bytes(b"data")
        mocker.patch("utils.zip_cache.LIBRARY_BASE_PATH", str(lib))
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path / "cache"))

        result = build_cached_zip(
            namespace="42",
            entries=[ZipFileEntry("a.bin", "roms/a.bin", 4, 1000.0)],
            m3u_content=b"a.bin",
            m3u_filename="game.m3u",
            cache_key="key",
        )
        with ZipFile(result) as zf:
            assert zf.read("a.bin") == b"data"
            assert zf.read("game.m3u") == b"a.bin"


class TestConstants:
    def test_bulk_cache_max_roms(self):
        assert BULK_CACHE_MAX_ROMS == 100

    def test_large_zip_threshold(self):
        assert LARGE_ZIP_THRESHOLD_BYTES == 8 * 1024 * 1024 * 1024

    def test_ttl_values(self):
        assert DEFAULT_TTL_HOURS == 48
        assert LARGE_ZIP_TTL_HOURS == 12
