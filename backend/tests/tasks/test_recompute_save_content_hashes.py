"""Tests for RecomputeSaveContentHashesTask.

Background lives in commit 7996c1293: every zip save's content_hash was
incorrectly stored as the raw MD5 of the zip wrapper instead of the
per-entry zip-hash. This task walks every Save row, recomputes via the
fixed dispatch, and rewrites stale values. These tests pin the
update / unchanged / missing-fs accounting.

ZIP_STORED is used everywhere so the wrapper bytes are deterministic and
the pinned per-entry digests stay valid.
"""

import hashlib
import zipfile
from pathlib import Path

import pytest
from tests._zipfile_shim import reload_zipfile

from handler.database import db_save_handler
from handler.filesystem import fs_asset_handler
from models.assets import Save
from models.platform import Platform
from models.rom import Rom
from models.user import User
from tasks.manual.recompute_save_content_hashes import (
    RecomputeSaveContentHashesTask,
    recompute_save_content_hashes_task,
)

FIXTURE_A_PINNED_HASH = "b3636b49ca5c3d807adee33e75d410ca"


def _write_fixture_a_zip(target: Path) -> bytes:
    """Write the shared Fixture A zip to target; return the raw bytes."""
    target.parent.mkdir(parents=True, exist_ok=True)
    reload_zipfile()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("save.bin", b"\x42" * 256)
    return target.read_bytes()


@pytest.fixture
def isolated_assets_dir(tmp_path, monkeypatch):
    """Redirect fs_asset_handler to tmp_path so writes/lookups stay scoped."""
    new_base = Path(tmp_path).resolve()
    monkeypatch.setattr(fs_asset_handler, "base_path", new_base)
    return new_base


class TestRecomputeSaveContentHashesTask:
    @pytest.fixture
    def task(self) -> RecomputeSaveContentHashesTask:
        return RecomputeSaveContentHashesTask()

    def test_module_singleton_exists(self):
        assert recompute_save_content_hashes_task is not None
        assert isinstance(
            recompute_save_content_hashes_task, RecomputeSaveContentHashesTask
        )

    def test_init(self, task: RecomputeSaveContentHashesTask):
        assert task.title == "Recompute save content hashes"
        assert task.manual_run is True
        assert task.cron_string is None

    async def test_correct_hash_is_unchanged(
        self,
        task: RecomputeSaveContentHashesTask,
        isolated_assets_dir: Path,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        """A save whose stored hash already matches must not be rewritten."""
        rel_dir = f"{platform.fs_slug}/saves/test_emulator"
        file_name = "correct.zip"
        zip_path = isolated_assets_dir / rel_dir / file_name
        _write_fixture_a_zip(zip_path)

        save = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=file_name,
                file_name_no_tags="correct",
                file_name_no_ext="correct",
                file_extension="zip",
                emulator="test_emulator",
                slot="autosave",
                file_path=rel_dir,
                file_size_bytes=zip_path.stat().st_size,
                content_hash=FIXTURE_A_PINNED_HASH,
            )
        )

        stats = await task.run()

        assert stats["saves_scanned"] == 1
        assert stats["saves_unchanged"] == 1
        assert stats["saves_updated"] == 0
        assert stats["saves_missing_fs"] == 0
        assert stats["errors"] == 0

        refreshed = db_save_handler.get_save(user_id=admin_user.id, id=save.id)
        assert refreshed is not None
        assert refreshed.content_hash == FIXTURE_A_PINNED_HASH

    async def test_stale_raw_md5_is_rewritten_to_zip_hash(
        self,
        task: RecomputeSaveContentHashesTask,
        isolated_assets_dir: Path,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        """A zip save whose stored hash is the raw wrapper MD5 (the pre-fix
        value) must be rewritten to the per-entry zip-hash. This is the exact
        recovery the task exists for."""
        rel_dir = f"{platform.fs_slug}/saves/test_emulator"
        file_name = "stale.zip"
        zip_path = isolated_assets_dir / rel_dir / file_name
        raw_bytes = _write_fixture_a_zip(zip_path)

        # Pre-fix value: raw MD5 of the zip wrapper, not the per-entry digest.
        stale_raw_md5 = hashlib.md5(raw_bytes, usedforsecurity=False).hexdigest()
        assert stale_raw_md5 != FIXTURE_A_PINNED_HASH

        save = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=file_name,
                file_name_no_tags="stale",
                file_name_no_ext="stale",
                file_extension="zip",
                emulator="test_emulator",
                slot="autosave",
                file_path=rel_dir,
                file_size_bytes=zip_path.stat().st_size,
                content_hash=stale_raw_md5,
            )
        )

        stats = await task.run()

        assert stats["saves_scanned"] == 1
        assert stats["saves_updated"] == 1
        assert stats["saves_unchanged"] == 0
        assert stats["saves_missing_fs"] == 0
        assert stats["errors"] == 0

        refreshed = db_save_handler.get_save(user_id=admin_user.id, id=save.id)
        assert refreshed is not None
        assert refreshed.content_hash == FIXTURE_A_PINNED_HASH

    async def test_raw_md5_non_zip_correct_hash_is_unchanged(
        self,
        task: RecomputeSaveContentHashesTask,
        isolated_assets_dir: Path,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        """A non-zip save (e.g. raw .sav) whose stored hash already matches
        the raw MD5 of its bytes must not be rewritten. This exercises the
        _compute_file_hash dispatch path that the zip-only suite missed.
        """
        rel_dir = f"{platform.fs_slug}/saves/test_emulator"
        file_name = "raw_correct.sav"
        sav_path = isolated_assets_dir / rel_dir / file_name
        sav_path.parent.mkdir(parents=True, exist_ok=True)
        sav_bytes = b"raw save bytes, definitely not a zip"
        sav_path.write_bytes(sav_bytes)
        # Sanity: this file must NOT look like a zip to the dispatch.
        assert not zipfile.is_zipfile(sav_path)

        raw_md5 = hashlib.md5(sav_bytes, usedforsecurity=False).hexdigest()
        save = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=file_name,
                file_name_no_tags="raw_correct",
                file_name_no_ext="raw_correct",
                file_extension="sav",
                emulator="test_emulator",
                slot="autosave",
                file_path=rel_dir,
                file_size_bytes=sav_path.stat().st_size,
                content_hash=raw_md5,
            )
        )

        stats = await task.run()

        assert stats["saves_scanned"] == 1
        assert stats["saves_unchanged"] == 1
        assert stats["saves_updated"] == 0
        assert stats["saves_missing_fs"] == 0
        assert stats["errors"] == 0

        refreshed = db_save_handler.get_save(user_id=admin_user.id, id=save.id)
        assert refreshed is not None
        assert refreshed.content_hash == raw_md5

    async def test_raw_md5_non_zip_stale_hash_is_rewritten(
        self,
        task: RecomputeSaveContentHashesTask,
        isolated_assets_dir: Path,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        """A non-zip save whose stored hash is wrong must be rewritten to the
        raw MD5 of its bytes. This pins that the dispatch correctly routes
        non-zip files to _compute_file_hash and not _compute_zip_hash.
        """
        rel_dir = f"{platform.fs_slug}/saves/test_emulator"
        file_name = "raw_stale.sav"
        sav_path = isolated_assets_dir / rel_dir / file_name
        sav_path.parent.mkdir(parents=True, exist_ok=True)
        sav_bytes = b"\x00\x01\x02arbitrary bytes\xff\xfe"
        sav_path.write_bytes(sav_bytes)
        assert not zipfile.is_zipfile(sav_path)

        raw_md5 = hashlib.md5(sav_bytes, usedforsecurity=False).hexdigest()
        stale_hash = "0" * 32
        assert stale_hash != raw_md5

        save = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=file_name,
                file_name_no_tags="raw_stale",
                file_name_no_ext="raw_stale",
                file_extension="sav",
                emulator="test_emulator",
                slot="autosave",
                file_path=rel_dir,
                file_size_bytes=sav_path.stat().st_size,
                content_hash=stale_hash,
            )
        )

        stats = await task.run()

        assert stats["saves_scanned"] == 1
        assert stats["saves_updated"] == 1
        assert stats["saves_unchanged"] == 0
        assert stats["saves_missing_fs"] == 0
        assert stats["errors"] == 0

        refreshed = db_save_handler.get_save(user_id=admin_user.id, id=save.id)
        assert refreshed is not None
        assert refreshed.content_hash == raw_md5

    async def test_raw_md5_non_zip_routes_through_compute_file_hash(
        self,
        task: RecomputeSaveContentHashesTask,
        isolated_assets_dir: Path,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        """Direct dispatch check: for a non-zip file, compute_content_hash
        must call _compute_file_hash, not _compute_zip_hash. Spying on both
        nails down the routing in a way the hash-equality assertions don't.
        """
        from unittest.mock import patch

        from handler.filesystem import fs_asset_handler

        rel_dir = f"{platform.fs_slug}/saves/test_emulator"
        file_name = "raw_spy.sav"
        sav_path = isolated_assets_dir / rel_dir / file_name
        sav_path.parent.mkdir(parents=True, exist_ok=True)
        sav_path.write_bytes(b"spy on me")
        assert not zipfile.is_zipfile(sav_path)

        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=file_name,
                file_name_no_tags="raw_spy",
                file_name_no_ext="raw_spy",
                file_extension="sav",
                emulator="test_emulator",
                slot="autosave",
                file_path=rel_dir,
                file_size_bytes=sav_path.stat().st_size,
                content_hash="anything",
            )
        )

        original_file_hash = fs_asset_handler._compute_file_hash
        original_zip_hash = fs_asset_handler._compute_zip_hash

        with patch.object(
            fs_asset_handler,
            "_compute_file_hash",
            wraps=original_file_hash,
        ) as spy_file, patch.object(
            fs_asset_handler,
            "_compute_zip_hash",
            wraps=original_zip_hash,
        ) as spy_zip:
            await task.run()

        assert spy_file.call_count == 1
        assert spy_zip.call_count == 0

    async def test_missing_file_is_counted_but_unchanged(
        self,
        task: RecomputeSaveContentHashesTask,
        isolated_assets_dir: Path,
        admin_user: User,
        rom: Rom,
        platform: Platform,
    ):
        """A DB row whose backing file is gone must be tallied as missing_fs
        and the stored hash must be left alone (no overwrite-to-None)."""
        rel_dir = f"{platform.fs_slug}/saves/test_emulator"
        file_name = "ghost.zip"

        original_hash = "deadbeefdeadbeefdeadbeefdeadbeef"
        save = db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=file_name,
                file_name_no_tags="ghost",
                file_name_no_ext="ghost",
                file_extension="zip",
                emulator="test_emulator",
                slot="autosave",
                file_path=rel_dir,
                file_size_bytes=1,
                content_hash=original_hash,
            )
        )

        # Sanity: ensure the file really isn't on disk.
        assert not (isolated_assets_dir / rel_dir / file_name).exists()

        stats = await task.run()

        assert stats["saves_scanned"] == 1
        assert stats["saves_missing_fs"] == 1
        assert stats["saves_updated"] == 0
        assert stats["saves_unchanged"] == 0
        assert stats["errors"] == 0

        refreshed = db_save_handler.get_save(user_id=admin_user.id, id=save.id)
        assert refreshed is not None
        assert refreshed.content_hash == original_hash

    async def test_update_save_failure_increments_errors(
        self,
        task: RecomputeSaveContentHashesTask,
        isolated_assets_dir: Path,
        admin_user: User,
        rom: Rom,
        platform: Platform,
        mocker,
    ):
        """A row whose hash genuinely needs rewriting but whose update_save
        call raises should land in the errors bucket, not silently succeed."""
        rel_dir = f"{platform.fs_slug}/saves/test_emulator"
        file_name = "fixture_a.zip"
        _write_fixture_a_zip(isolated_assets_dir / rel_dir / file_name)

        db_save_handler.add_save(
            Save(
                rom_id=rom.id,
                user_id=admin_user.id,
                file_name=file_name,
                file_name_no_tags="fixture_a",
                file_name_no_ext="fixture_a",
                file_extension="zip",
                emulator="test_emulator",
                slot="autosave",
                file_path=rel_dir,
                file_size_bytes=1,
                content_hash="00000000000000000000000000000000",
            )
        )

        mocker.patch.object(
            db_save_handler,
            "update_save",
            side_effect=RuntimeError("simulated DB failure"),
        )

        stats = await task.run()

        assert stats["saves_scanned"] == 1
        assert stats["errors"] == 1
        assert stats["saves_updated"] == 0
        assert stats["saves_unchanged"] == 0
        assert stats["saves_missing_fs"] == 0
