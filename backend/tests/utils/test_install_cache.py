from datetime import datetime, timezone

import pytest

import utils.install_cache as install_cache
from utils.install_cache import (
    UNLIMITED_TTL,
    cache_size_bytes,
    clear_session_cache,
    ensure_session_cache_dir,
    resolve_expires_at,
    session_cache_dir,
)


@pytest.fixture
def cache_root(tmp_path, monkeypatch):
    root = tmp_path / "installs"
    monkeypatch.setattr(install_cache, "INSTALL_CACHE_PATH", str(root))
    return root


class TestResolveExpiresAt:
    def test_none_is_unlimited_by_default(self, monkeypatch):
        monkeypatch.setattr(
            install_cache.cm, "get_config", lambda: install_cache.cm.config
        )
        monkeypatch.setattr(install_cache.cm.config, "INSTALL_CACHE_TTL_DAYS", 0)
        assert resolve_expires_at(None) is None

    def test_unlimited_returns_none(self):
        assert resolve_expires_at(UNLIMITED_TTL) is None

    def test_zero_returns_none(self):
        assert resolve_expires_at(0) is None

    def test_positive_ttl_in_future(self):
        before = datetime.now(timezone.utc)
        expires = resolve_expires_at(3600)
        assert expires is not None
        delta = (expires - before).total_seconds()
        assert 3595 <= delta <= 3605


class TestSessionCacheDir:
    def test_path_under_cache_root(self, cache_root):
        assert session_cache_dir(42) == cache_root / "42"

    def test_ensure_creates_dir(self, cache_root):
        path = ensure_session_cache_dir(7)
        assert path.exists()
        assert path.is_dir()


class TestClearSessionCache:
    def test_missing_returns_false(self, cache_root):
        assert clear_session_cache(99) is False

    def test_removes_existing(self, cache_root):
        path = ensure_session_cache_dir(1)
        (path / "file.bin").write_bytes(b"x" * 10)
        assert clear_session_cache(1) is True
        assert not path.exists()


class TestCacheSizeBytes:
    def test_empty_when_missing(self, cache_root):
        assert cache_size_bytes(123) == 0

    def test_sums_nested_files(self, cache_root):
        path = ensure_session_cache_dir(2)
        (path / "a.bin").write_bytes(b"x" * 100)
        nested = path / "sub"
        nested.mkdir()
        (nested / "b.bin").write_bytes(b"y" * 50)
        assert cache_size_bytes(2) == 150


class TestDirSizeBytes:
    def test_hardlinked_files_count_once(self, cache_root):
        path = ensure_session_cache_dir(3)
        original = path / "prefix" / "game.dll"
        original.parent.mkdir()
        original.write_bytes(b"x" * 100)
        (path / "game.dll").hardlink_to(original)
        assert install_cache.dir_size_bytes(path) == 100

    def test_cache_root_dirs_lists_session_directories(self, cache_root):
        ensure_session_cache_dir(4)
        ensure_session_cache_dir(5)
        assert [p.name for p in install_cache.cache_root_dirs()] == ["4", "5"]


class TestConfiguredTtl:
    def test_zero_days_is_unlimited(self, monkeypatch):
        monkeypatch.setattr(install_cache.cm.config, "INSTALL_CACHE_TTL_DAYS", 0)
        monkeypatch.setattr(
            install_cache.cm, "get_config", lambda: install_cache.cm.config
        )
        assert resolve_expires_at(None) is None

    def test_days_setting_drives_the_default(self, monkeypatch):
        monkeypatch.setattr(install_cache.cm.config, "INSTALL_CACHE_TTL_DAYS", 3)
        monkeypatch.setattr(
            install_cache.cm, "get_config", lambda: install_cache.cm.config
        )
        before = datetime.now(timezone.utc)
        expires = resolve_expires_at(None)
        assert expires is not None
        assert 3 * 86400 - 5 <= (expires - before).total_seconds() <= 3 * 86400 + 5


class TestPurgeSuperseded:
    def test_removes_finished_older_sessions_but_not_active_or_kept(
        self, cache_root, monkeypatch
    ):
        from types import SimpleNamespace

        from models.install_session import InstallSessionState as S

        rows = {
            1: S.DONE,
            2: S.FAILED,
            3: S.INSTALLING,
            4: S.DONE,
        }
        deleted = []
        fake = SimpleNamespace(
            get_sessions_for_rom=lambda rom_id: [
                SimpleNamespace(id=i, state=st, user_id=7) for i, st in rows.items()
            ],
            delete_session=deleted.append,
        )
        import handler.database as db

        monkeypatch.setattr(db, "db_install_session_handler", fake)
        for i in rows:
            ensure_session_cache_dir(i)
        removed = install_cache.purge_superseded_sessions(
            10, keep_session_id=4, owner_user_id=7
        )
        assert removed == 2
        assert sorted(deleted) == [1, 2]
        assert not session_cache_dir(1).exists()
        assert session_cache_dir(3).exists() and session_cache_dir(4).exists()

    def test_never_touches_a_different_users_session(self, cache_root, monkeypatch):
        from types import SimpleNamespace

        from models.install_session import InstallSessionState as S

        deleted = []
        fake = SimpleNamespace(
            get_sessions_for_rom=lambda rom_id: [
                SimpleNamespace(id=1, state=S.DONE, user_id=7),
                SimpleNamespace(id=2, state=S.DONE, user_id=8),
            ],
            delete_session=deleted.append,
        )
        import handler.database as db

        monkeypatch.setattr(db, "db_install_session_handler", fake)
        for i in (1, 2):
            ensure_session_cache_dir(i)
        removed = install_cache.purge_superseded_sessions(
            10, keep_session_id=99, owner_user_id=7
        )
        assert removed == 0
        assert deleted == []
        assert session_cache_dir(2).exists()
