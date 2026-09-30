import os
import time

import pytest

import tasks.scheduled.cleanup_upload_tmp as mod
from tasks.scheduled.cleanup_upload_tmp import CleanupUploadTmpTask


class TestCleanupUploadTmpTask:
    @pytest.fixture
    def task(self):
        return CleanupUploadTmpTask()

    def test_init(self, task):
        """Test task initialization"""
        assert task.enabled is True
        assert task.cron_string == "0 * * * *"

    def test_custom_schedule(self, monkeypatch):
        monkeypatch.setattr(mod, "SCHEDULED_CLEANUP_UPLOAD_TMP_CRON", "0 2 * * *")
        assert CleanupUploadTmpTask().cron_string == "0 2 * * *"

    async def test_run_no_tmp_dir(self, task, monkeypatch, tmp_path):
        """Task is a no-op when the uploads tmp directory does not exist."""
        monkeypatch.setattr(mod, "ROM_UPLOAD_TMP_BASE", tmp_path / "nonexistent")
        # Should complete without error
        await task.run()

    async def test_run_removes_expired_dirs(self, task, monkeypatch, tmp_path):
        """Directories whose mtime is older than ROM_UPLOAD_TTL should be removed."""
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        monkeypatch.setattr(mod, "ROM_UPLOAD_TMP_BASE", uploads)
        monkeypatch.setattr(mod, "ROM_UPLOAD_TTL", 3600)

        old_dir = uploads / "old-upload"
        old_dir.mkdir()
        # Backdate mtime to 2 hours ago
        old_ts = time.time() - 7200
        os.utime(old_dir, (old_ts, old_ts))

        await task.run()

        assert not old_dir.exists()

    async def test_run_keeps_recent_dirs(self, task, monkeypatch, tmp_path):
        """Directories whose mtime is within ROM_UPLOAD_TTL should be kept."""
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        monkeypatch.setattr(mod, "ROM_UPLOAD_TMP_BASE", uploads)
        monkeypatch.setattr(mod, "ROM_UPLOAD_TTL", 3600)

        recent_dir = uploads / "recent-upload"
        recent_dir.mkdir()
        # mtime is now (within TTL)

        await task.run()

        assert recent_dir.exists()

    async def test_run_skips_files(self, task, monkeypatch, tmp_path):
        """Files (not directories) in the uploads root are left untouched."""
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        monkeypatch.setattr(mod, "ROM_UPLOAD_TMP_BASE", uploads)
        monkeypatch.setattr(mod, "ROM_UPLOAD_TTL", 3600)

        stale_file = uploads / "stale.tmp"
        stale_file.write_bytes(b"data")
        old_ts = time.time() - 7200
        os.utime(stale_file, (old_ts, old_ts))

        await task.run()

        assert stale_file.exists()

    async def test_disabled_cleanup_keeps_expired_upload(self, monkeypatch, tmp_path):
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        expired = uploads / "expired"
        expired.mkdir()
        os.utime(expired, (0, 0))
        monkeypatch.setattr(mod, "ROM_UPLOAD_TMP_BASE", uploads)
        monkeypatch.setattr(mod, "ENABLE_SCHEDULED_CLEANUP_UPLOAD_TMP", False)
        task = CleanupUploadTmpTask()
        assert task.enabled is False
        await task.run()
        assert expired.exists()
