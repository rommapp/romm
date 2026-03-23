import os
import time
from zipfile import ZipFile

import pytest

from utils.zip_cache import (
    ZipFileEntry,
    build_cached_zip,
    cleanup_stale_zips,
    get_cache_key,
    get_cached_zip,
    get_zip_redirect_path,
    has_space_for_cache,
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
        key1 = get_cache_key(1, entries, False)
        key2 = get_cache_key(1, entries, False)
        assert key1 == key2

    def test_different_rom_ids(self):
        entries = [_entry()]
        assert get_cache_key(1, entries, False) != get_cache_key(2, entries, False)

    def test_different_hidden_folder(self):
        entries = [_entry()]
        assert get_cache_key(1, entries, False) != get_cache_key(1, entries, True)

    def test_different_files(self):
        e1 = [_entry("a.bin")]
        e2 = [_entry("b.bin")]
        assert get_cache_key(1, e1, False) != get_cache_key(1, e2, False)

    def test_different_updated_at(self):
        e1 = [_entry(epoch=1000.0)]
        e2 = [_entry(epoch=2000.0)]
        assert get_cache_key(1, e1, False) != get_cache_key(1, e2, False)

    def test_order_independent(self):
        entries_a = [_entry("a.bin", 100), _entry("b.bin", 200)]
        entries_b = [_entry("b.bin", 200), _entry("a.bin", 100)]
        assert get_cache_key(1, entries_a, False) == get_cache_key(1, entries_b, False)

    def test_returns_hex_string(self):
        key = get_cache_key(1, [_entry()], False)
        assert len(key) == 16
        int(key, 16)  # should not raise

    def test_file_change_invalidates_cache(self):
        entries_v1 = [
            _entry("disc1.chd", 500, epoch=1000.0),
            _entry("disc2.chd", 600, epoch=1000.0),
        ]
        entries_v2 = [
            _entry("disc1.chd", 500, epoch=1000.0),
            _entry("disc2.chd", 600, epoch=2000.0),
        ]
        assert get_cache_key(1, entries_v1, False) != get_cache_key(
            1, entries_v2, False
        )

    def test_file_size_change_invalidates_cache(self):
        e1 = [_entry("game.bin", size=1000, epoch=1000.0)]
        e2 = [_entry("game.bin", size=2000, epoch=1000.0)]
        assert get_cache_key(1, e1, False) != get_cache_key(1, e2, False)


class TestGetCachedZip:
    def test_returns_none_when_missing(self, tmp_path, mocker):
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert get_cached_zip(1, "abc123") is None

    def test_returns_path_when_exists(self, tmp_path, mocker):
        rom_dir = tmp_path / "1"
        rom_dir.mkdir()
        (rom_dir / "abc123.zip").write_bytes(b"fake")
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        result = get_cached_zip(1, "abc123")
        assert result is not None
        assert result.name == "abc123.zip"

    def test_old_key_not_returned_for_new_key(self, tmp_path, mocker):
        rom_dir = tmp_path / "1"
        rom_dir.mkdir()
        (rom_dir / "oldkey.zip").write_bytes(b"old content")
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert get_cached_zip(1, "oldkey") is not None
        assert get_cached_zip(1, "newkey") is None


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
            rom_id=42,
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
            rom_id=42,
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
            rom_id=42,
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
                rom_id=42,
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
            rom_id=42,
            entries=entries,
            m3u_content=None,
            m3u_filename=None,
            cache_key="newkey",
        )

        assert old_zip.exists(), "Old cache must not be deleted during build"
        assert (rom_cache / "newkey.zip").exists()


class TestGetZipRedirectPath:
    def test_returns_correct_path(self):
        result = get_zip_redirect_path(42, "abc123")
        assert str(result) == "/cache/zips/42/abc123.zip"


class TestHasSpaceForCache:
    def test_returns_true_with_enough_space(self, tmp_path, mocker):
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert has_space_for_cache([_entry(size=1024)]) is True

    def test_returns_false_with_insufficient_space(self, tmp_path, mocker):
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert has_space_for_cache([_entry(size=2**62)]) is False

    def test_requires_2x_buffer(self, tmp_path, mocker):
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        stat = os.statvfs(tmp_path)
        available = stat.f_bavail * stat.f_frsize
        size_just_over_half = int(available * 0.6)
        assert has_space_for_cache([_entry(size=size_just_over_half)]) is False


class TestCleanupStaleZips:
    def test_deletes_old_files(self, tmp_path, mocker):
        rom_dir = tmp_path / "1"
        rom_dir.mkdir()
        old_zip = rom_dir / "old.zip"
        old_zip.write_bytes(b"stale")
        old_time = time.time() - (72 * 3600)
        os.utime(old_zip, (old_time, old_time))

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert cleanup_stale_zips(max_age_hours=48) == 1
        assert not old_zip.exists()

    def test_keeps_recent_files(self, tmp_path, mocker):
        rom_dir = tmp_path / "1"
        rom_dir.mkdir()
        recent = rom_dir / "recent.zip"
        recent.write_bytes(b"fresh")

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert cleanup_stale_zips(max_age_hours=48) == 0
        assert recent.exists()

    def test_removes_empty_directories(self, tmp_path, mocker):
        rom_dir = tmp_path / "1"
        rom_dir.mkdir()
        old_zip = rom_dir / "old.zip"
        old_zip.write_bytes(b"stale")
        old_time = time.time() - (72 * 3600)
        os.utime(old_zip, (old_time, old_time))

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        cleanup_stale_zips(max_age_hours=48)
        assert not rom_dir.exists()

    def test_handles_missing_cache_dir(self, tmp_path, mocker):
        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path / "nonexistent"))
        assert cleanup_stale_zips(max_age_hours=48) == 0

    def test_keeps_dir_with_remaining_files(self, tmp_path, mocker):
        rom_dir = tmp_path / "1"
        rom_dir.mkdir()

        old_zip = rom_dir / "old.zip"
        old_zip.write_bytes(b"stale")
        old_time = time.time() - (72 * 3600)
        os.utime(old_zip, (old_time, old_time))

        fresh_zip = rom_dir / "fresh.zip"
        fresh_zip.write_bytes(b"current")

        mocker.patch("utils.zip_cache.ZIP_CACHE_PATH", str(tmp_path))
        assert cleanup_stale_zips(max_age_hours=48) == 1
        assert not old_zip.exists()
        assert fresh_zip.exists()
        assert rom_dir.exists()
