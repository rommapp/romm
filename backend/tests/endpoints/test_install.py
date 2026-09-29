import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from tests.endpoints.test_music import _auth  # noqa: F401

import endpoints.roms.install as install_module
import utils.install_cache as install_cache
from config import ROMM_BASE_URL
from handler.database import (
    db_install_session_handler,
    db_platform_handler,
    db_rom_handler,
)
from handler.filesystem.installer_detection import InstallerCandidate
from handler.install import bandwidth, stream_presence
from handler.install.manifest import (
    LiveManifestEntry,
    build_manifest,
    write_live_manifest,
    write_manifest,
)
from models.install_session import InstallSession, InstallSessionState
from models.platform import Platform
from models.rom import Rom
from models.user import User


@pytest.fixture
def install_cache_root(tmp_path, monkeypatch):
    root = tmp_path / "installs"
    monkeypatch.setattr(install_cache, "INSTALL_CACHE_PATH", str(root))
    return root


@pytest.fixture
def win_platform():
    platform = Platform(name="Windows", slug="win", fs_slug="win")
    return db_platform_handler.add_platform(platform)


@pytest.fixture
def win_rom(admin_user: User, win_platform: Platform):
    rom = Rom(
        platform_id=win_platform.id,
        name="test_win_rom",
        slug="test_win_rom_slug",
        fs_name="test_win_rom",
        fs_name_no_tags="test_win_rom",
        fs_name_no_ext="test_win_rom",
        fs_extension="",
        fs_path=f"{win_platform.slug}/roms",
    )
    rom = db_rom_handler.add_rom(rom)
    db_rom_handler.add_rom_user(rom_id=rom.id, user_id=admin_user.id)
    return rom


class TestGetInstallCandidates:
    def test_non_windows_rom_flags_stream_copy(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        r = client.get(
            f"/api/roms/{rom.id}/install/candidates", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["stream_copy"] is True
        assert body["needs_manual_pick"] is False

    def test_windows_rom_with_no_files_needs_manual_pick(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        r = client.get(
            f"/api/roms/{win_rom.id}/install/candidates",
            headers=_auth(access_token),
        )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["stream_copy"] is False
        assert body["needs_manual_pick"] is True
        assert body["candidates"] == []

    def test_unknown_rom_404s(self, client: TestClient, access_token: str):
        r = client.get(
            "/api/roms/999999/install/candidates", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_works_without_a_worker(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        # Purely a filesystem scan - no job is enqueued, so this must not
        # require an install-sandbox worker to be connected (manual mode
        # relies on candidates/manual_install_url being available even when
        # no worker is registered, see start_install_session's docstring).
        with patch("endpoints.roms.install.has_install_worker", return_value=False):
            r = client.get(
                f"/api/roms/{rom.id}/install/candidates", headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK


class TestStartInstallSession:
    def test_no_worker_by_default(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        r = client.post(
            f"/api/roms/{rom.id}/install", json={}, headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_non_windows_rom_starts_streaming_immediately(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        # Regression guard: this deliberately does NOT mock count_running_sessions
        # or raise INSTALL_MAX_CONCURRENCY. A session created directly in
        # STREAMING (a "running" state) before the concurrency check runs would
        # count against itself and always 429 here, since the default cap is 1.
        with (
            patch("endpoints.roms.install.has_install_worker", return_value=True),
            patch(
                "endpoints.roms.install.enqueue_stream_copy", return_value="job-456"
            ) as mock_enqueue,
        ):
            r = client.post(
                f"/api/roms/{rom.id}/install", json={}, headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["state"] == InstallSessionState.STREAMING.value
        mock_enqueue.assert_called_once()

    def test_windows_rom_without_installer_path_awaits_manual_pick(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        # No worker mocked: this returns before that check even runs (nothing
        # to enqueue yet). win_rom has no real files on disk, so there is no
        # candidate to pick by default - a human has to choose, hence
        # AWAITING_INSTALLER with a URL to send them to (see
        # manual_install_url's own docstring).
        r = client.post(
            f"/api/roms/{win_rom.id}/install", json={}, headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["state"] == InstallSessionState.AWAITING_INSTALLER.value
        assert body["manual_install_url"] == f"{ROMM_BASE_URL}/rom/{win_rom.id}/install"

    def test_windows_rom_auto_picks_a_confident_installer(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        # The server resolves the installer itself (the top candidate, as the
        # Install page pre-selects it), so no client has to fetch candidates
        # and pick one just to start.
        candidate = InstallerCandidate(
            path="setup.exe",
            file_name="setup.exe",
            file_size_bytes=123,
            rank=0,
            kind="known installer",
        )
        with (
            patch(
                "endpoints.roms.install.fs_rom_handler.get_installer_candidates",
                return_value=[candidate],
            ),
            patch("endpoints.roms.install.has_install_worker", return_value=True),
            patch(
                "endpoints.roms.install.enqueue_install", return_value="job-999"
            ) as mock_enqueue,
        ):
            r = client.post(
                f"/api/roms/{win_rom.id}/install", json={}, headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["state"] == InstallSessionState.INSTALLING.value
        assert body["installer_path"] == "setup.exe"
        mock_enqueue.assert_called_once()

    def test_windows_rom_defaults_to_an_archive_as_the_source(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        candidate = InstallerCandidate(
            path="MyGame.zip",
            file_name="MyGame.zip",
            file_size_bytes=123,
            rank=4,
            kind="archive",
        )
        with (
            patch(
                "endpoints.roms.install.fs_rom_handler.get_installer_candidates",
                return_value=[candidate],
            ),
            patch("endpoints.roms.install.has_install_worker", return_value=True),
            patch("endpoints.roms.install.enqueue_install", return_value="job-1"),
        ):
            r = client.post(
                f"/api/roms/{win_rom.id}/install", json={}, headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["state"] == InstallSessionState.INSTALLING.value
        assert body["source_path"] == "MyGame.zip"
        assert body["installer_path"] is None

    def test_already_done_session_does_not_block_a_fresh_install(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        # There's no separate "Reinstall" concept - pressing Install always
        # starts a genuinely new attempt, even over an existing DONE
        # session (a client that wants "already installed, just stream it,
        # don't touch anything" - the CLI's own default - checks
        # GET /{id}/install itself first and never reaches this POST at all;
        # see start_install_session's own docstring).
        done = db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.DONE,
                installer_path="setup.exe",
            )
        )
        with (
            patch("endpoints.roms.install.has_install_worker", return_value=True),
            patch(
                "endpoints.roms.install.enqueue_install", return_value="job-fresh"
            ) as mock_enqueue,
        ):
            r = client.post(
                f"/api/roms/{win_rom.id}/install",
                json={"installer_path": "setup.exe"},
                headers=_auth(access_token),
            )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["id"] != done.id
        assert body["state"] == InstallSessionState.INSTALLING.value
        mock_enqueue.assert_called_once()

    def test_windows_rom_with_installer_path_enqueues(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        with (
            patch("endpoints.roms.install.has_install_worker", return_value=True),
            patch(
                "endpoints.roms.install.enqueue_install", return_value="job-123"
            ) as mock_enqueue,
        ):
            r = client.post(
                f"/api/roms/{win_rom.id}/install",
                json={"installer_path": "setup.exe"},
                headers=_auth(access_token),
            )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["state"] == InstallSessionState.INSTALLING.value
        mock_enqueue.assert_called_once()

    def test_auto_mode_is_off_by_default_and_opt_in_per_request(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        with (
            patch("endpoints.roms.install.has_install_worker", return_value=True),
            patch("endpoints.roms.install.enqueue_install", return_value="job-1"),
        ):
            off = client.post(
                f"/api/roms/{win_rom.id}/install",
                json={"installer_path": "setup.exe"},
                headers=_auth(access_token),
            )
        assert off.status_code == status.HTTP_200_OK
        assert off.json()["auto_mode"] is False
        db_install_session_handler.delete_session(off.json()["id"])

        with (
            patch("endpoints.roms.install.has_install_worker", return_value=True),
            patch("endpoints.roms.install.enqueue_install", return_value="job-2"),
        ):
            on = client.post(
                f"/api/roms/{win_rom.id}/install",
                json={"installer_path": "setup.exe", "auto_mode": True},
                headers=_auth(access_token),
            )
        assert on.json()["auto_mode"] is True

    def test_proton_build_round_trips_into_the_session(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        with (
            patch("endpoints.roms.install.has_install_worker", return_value=True),
            patch("endpoints.roms.install.enqueue_install", return_value="job-123"),
        ):
            r = client.post(
                f"/api/roms/{win_rom.id}/install",
                json={"installer_path": "setup.exe", "proton_build": "GE-Proton10-34"},
                headers=_auth(access_token),
            )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["proton_build"] == "GE-Proton10-34"

    def test_reuses_existing_active_session(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        # Neither call ever reaches the worker check: the first has no
        # installer_path (returns early), the second finds the first's
        # still-active session and returns it as-is.
        first = client.post(
            f"/api/roms/{win_rom.id}/install", json={}, headers=_auth(access_token)
        ).json()
        second = client.post(
            f"/api/roms/{win_rom.id}/install", json={}, headers=_auth(access_token)
        ).json()
        assert first["id"] == second["id"]

    def test_installer_path_resumes_a_stuck_awaiting_session(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        # Regression guard: a session left in AWAITING_INSTALLER (auto-pick
        # found nothing confident) must not be stuck there forever - a later
        # request that finally supplies a path has to update and enqueue it,
        # not just hand back the same never-enqueued session again (the
        # "reuse" short-circuit is only for calls that bring nothing new).
        stuck = client.post(
            f"/api/roms/{win_rom.id}/install", json={}, headers=_auth(access_token)
        ).json()
        assert stuck["state"] == InstallSessionState.AWAITING_INSTALLER.value
        assert stuck["installer_path"] is None

        with (
            patch("endpoints.roms.install.has_install_worker", return_value=True),
            patch(
                "endpoints.roms.install.enqueue_install", return_value="job-789"
            ) as mock_enqueue,
        ):
            resumed = client.post(
                f"/api/roms/{win_rom.id}/install",
                json={"installer_path": "setup.exe"},
                headers=_auth(access_token),
            ).json()
        assert resumed["id"] == stuck["id"]
        assert resumed["state"] == InstallSessionState.INSTALLING.value
        assert resumed["installer_path"] == "setup.exe"
        mock_enqueue.assert_called_once()

    def test_concurrency_limit_rejects_and_cleans_up_session(
        self,
        client: TestClient,
        access_token: str,
        win_rom: Rom,
        admin_user: User,
    ):
        # No worker mocked: the concurrency check (which this forces to fail)
        # runs before the worker check, so it's never reached.
        with patch("endpoints.roms.install.INSTALL_MAX_CONCURRENCY", 0):
            r = client.post(
                f"/api/roms/{win_rom.id}/install",
                json={"installer_path": "setup.exe"},
                headers=_auth(access_token),
            )
        assert r.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        # The session created before the enqueue check must not be left behind.
        assert (
            db_install_session_handler.get_latest_session_for_rom(
                win_rom.id, admin_user.id
            )
            is None
        )

    def test_no_worker_rejects_and_cleans_up_session(
        self,
        client: TestClient,
        access_token: str,
        win_rom: Rom,
        admin_user: User,
    ):
        # Regression guard: enqueueing onto a queue nobody listens to would
        # leave the session stuck "installing" forever with no way to fail.
        with patch("endpoints.roms.install.has_install_worker", return_value=False):
            r = client.post(
                f"/api/roms/{win_rom.id}/install",
                json={"installer_path": "setup.exe"},
                headers=_auth(access_token),
            )
        assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert (
            db_install_session_handler.get_latest_session_for_rom(
                win_rom.id, admin_user.id
            )
            is None
        )


class TestClearInstallSession:
    def test_missing_session_404s(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        r = client.delete(f"/api/roms/{rom.id}/install", headers=_auth(access_token))
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_running_session_cannot_be_cleared(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
            )
        )
        r = client.delete(
            f"/api/roms/{win_rom.id}/install", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_409_CONFLICT
        assert db_install_session_handler.get_session(session.id) is not None

    def test_finished_session_can_be_cleared(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.DONE,
            )
        )
        r = client.delete(
            f"/api/roms/{win_rom.id}/install", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_200_OK
        assert db_install_session_handler.get_session(session.id) is None

    @pytest.mark.asyncio
    async def test_finished_session_with_an_active_downloader_cannot_be_cleared(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        # A DONE session's cache is exactly what a client keeps pulling files
        # from after the install finishes - clearing it out from under an
        # in-flight download is just as destructive as clearing a still-
        # running one, even though the session itself is no longer "active".
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.DONE,
            )
        )
        await stream_presence.heartbeat(session.id, user_id=99, device_id="steamdeck")

        r = client.delete(
            f"/api/roms/{win_rom.id}/install", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_409_CONFLICT
        assert db_install_session_handler.get_session(session.id) is not None

        # Once that client's presence naturally expires (or it disconnects),
        # clearing goes back to working normally - this isn't a permanent
        # lock, just a "not right now" while someone's actively reading it.
        with patch(
            "endpoints.roms.install.stream_presence.count_viewers",
            new=AsyncMock(return_value=0),
        ):
            r = client.delete(
                f"/api/roms/{win_rom.id}/install", headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK
        assert db_install_session_handler.get_session(session.id) is None


class TestCancelInstallSession:
    def test_missing_session_404s(
        self, client: TestClient, access_token: str, rom: Rom
    ):
        r = client.post(
            f"/api/roms/{rom.id}/install/cancel", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_terminal_session_409s(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        r = client.post(
            f"/api/roms/{win_rom.id}/install/cancel", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_409_CONFLICT

    def test_cancels_running_session_and_clears_cache(
        self,
        client: TestClient,
        access_token: str,
        win_rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
                job_id="job-abc",
                vnc_url="http://example.com/vnc.html",
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "partial.bin").write_bytes(b"incomplete")

        with patch("endpoints.roms.install.send_stop_job_command") as mock_stop:
            r = client.post(
                f"/api/roms/{win_rom.id}/install/cancel", headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["state"] == InstallSessionState.FAILED.value
        assert body["error"] == "Cancelled by user"
        assert body["vnc_url"] is None
        mock_stop.assert_called_once()
        assert mock_stop.call_args.args[1] == "job-abc"
        assert not cache_dir.exists()

    def test_survives_stop_command_failure(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        # The job may already be finished/gone by the time we ask - cancelling
        # still succeeds (it's the state+cache cleanup that matters).
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
                job_id="job-already-gone",
            )
        )
        with patch(
            "endpoints.roms.install.send_stop_job_command",
            side_effect=Exception("job not found"),
        ):
            r = client.post(
                f"/api/roms/{win_rom.id}/install/cancel", headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["state"] == InstallSessionState.FAILED.value

    def test_clear_cache_false_keeps_the_partial_download(
        self,
        client: TestClient,
        access_token: str,
        win_rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        # The web UI's own two-step abort confirmation ("keep the partial
        # download or clear it?") passes this when the user chose to keep
        # it - the session still stops, but nothing on disk is touched.
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "partial.bin").write_bytes(b"incomplete")

        r = client.post(
            f"/api/roms/{win_rom.id}/install/cancel?clear_cache=false",
            headers=_auth(access_token),
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["state"] == InstallSessionState.FAILED.value
        assert cache_dir.exists()
        assert (cache_dir / "partial.bin").is_file()


class TestInstallWorkerStatus:
    def test_reports_unavailable_by_default(
        self, client: TestClient, access_token: str
    ):
        r = client.get("/api/roms/install/worker-status", headers=_auth(access_token))
        assert r.status_code == status.HTTP_200_OK
        assert r.json() == {"available": False}

    def test_reports_available_when_worker_connected(
        self, client: TestClient, access_token: str
    ):
        with patch("endpoints.roms.install.has_install_worker", return_value=True):
            r = client.get(
                "/api/roms/install/worker-status", headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK
        assert r.json() == {"available": True}


class TestProtonBuilds:
    def test_lists_known_builds_with_exactly_one_installed(
        self, client: TestClient, access_token: str
    ):
        from handler.install.proton_builds import ProtonBuild

        with patch.object(
            install_module,
            "list_proton_builds",
            lambda: (
                ProtonBuild(
                    id="GE-Proton10-34",
                    label="GE-Proton 10-34",
                    installed=True,
                    path="/opt/proton/GE-Proton10-34/proton",
                ),
                ProtonBuild(
                    id="GE-Proton11-7",
                    label="GE-Proton 11-7",
                    installed=False,
                    source="upstream",
                    download_url="https://example.com/release.tar.gz",
                ),
            ),
        ):
            r = client.get(
                "/api/roms/install/proton-builds", headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK
        builds = r.json()["builds"]
        assert len(builds) > 0
        assert sum(1 for b in builds if b["installed"]) == 1


class TestInstallCacheManager:
    def _session(self, win_rom, admin_user, state, root):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=state,
                installer_path="setup.exe",
            )
        )
        cache_dir = root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "game.bin").write_bytes(b"x" * 100)
        return session

    def test_lists_caches_with_total(
        self, client, access_token, win_rom, admin_user, install_cache_root
    ):
        session = self._session(
            win_rom, admin_user, InstallSessionState.DONE, install_cache_root
        )
        r = client.get("/api/roms/install/cache", headers=_auth(access_token))
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["total_bytes"] == 100
        assert [(e["session_id"], e["size_bytes"]) for e in body["entries"]] == [
            (session.id, 100)
        ]

    def test_delete_one_removes_files_and_session(
        self, client, access_token, win_rom, admin_user, install_cache_root
    ):
        session = self._session(
            win_rom, admin_user, InstallSessionState.DONE, install_cache_root
        )
        r = client.delete(
            f"/api/roms/install/cache/{session.id}", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.json()["freed_bytes"] == 100
        assert not (install_cache_root / str(session.id)).exists()
        assert db_install_session_handler.get_session(session.id) is None

    def test_delete_one_refuses_a_running_install(
        self, client, access_token, win_rom, admin_user, install_cache_root
    ):
        session = self._session(
            win_rom, admin_user, InstallSessionState.INSTALLING, install_cache_root
        )
        r = client.delete(
            f"/api/roms/install/cache/{session.id}", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_409_CONFLICT
        assert (install_cache_root / str(session.id)).exists()

    def test_delete_all_skips_running_installs(
        self, client, access_token, win_rom, admin_user, install_cache_root
    ):
        done = self._session(
            win_rom, admin_user, InstallSessionState.DONE, install_cache_root
        )
        running = self._session(
            win_rom, admin_user, InstallSessionState.INSTALLING, install_cache_root
        )
        r = client.delete("/api/roms/install/cache", headers=_auth(access_token))
        assert r.status_code == status.HTTP_200_OK
        assert r.json() == {"removed": 1, "freed_bytes": 100, "skipped": 1}
        assert not (install_cache_root / str(done.id)).exists()
        assert (install_cache_root / str(running.id)).exists()


class TestCustomProtonBuilds:
    def test_add_lists_and_remove(self, client, access_token):
        saved: list[list[dict[str, str]]] = []
        current: list[dict[str, str]] = []

        def fake_update(**kwargs):
            current[:] = kwargs["custom_proton_builds"]
            saved.append(list(current))

        with (
            patch.object(install_module.cm, "update_install_settings", fake_update),
            patch.object(install_module, "get_custom_builds", lambda: list(current)),
            patch.object(install_module, "remove_build", lambda _id: None),
        ):
            r = client.post(
                "/api/roms/install/proton-builds/custom",
                json={"name": "My Proton", "url": "https://example.com/p.tar.gz"},
                headers=_auth(access_token),
            )
            assert r.status_code == status.HTTP_200_OK
            assert r.json()["id"] == "custom-my-proton"
            assert r.json()["custom"] is True

            dup = client.post(
                "/api/roms/install/proton-builds/custom",
                json={"name": "my proton", "url": "https://example.com/q.tar.gz"},
                headers=_auth(access_token),
            )
            assert dup.status_code == status.HTTP_409_CONFLICT

            gone = client.delete(
                "/api/roms/install/proton-builds/custom/custom-my-proton",
                headers=_auth(access_token),
            )
            assert gone.status_code == status.HTTP_200_OK
        assert saved[-1] == []

    def test_rejects_a_non_http_url(self, client, access_token):
        r = client.post(
            "/api/roms/install/proton-builds/custom",
            json={"name": "Bad", "url": "file:///etc/passwd"},
            headers=_auth(access_token),
        )
        assert r.status_code == status.HTTP_400_BAD_REQUEST


class TestAssertOwnsVncPort:
    """Pure unit coverage of the ownership check both VNC proxy routes
    (install_vnc_http, install_vnc_ws) share - see TestInstallVncHttp for the
    HTTP route wired end to end."""

    def test_raises_403_with_no_matching_session(self, admin_user: User):
        with pytest.raises(HTTPException) as exc_info:
            install_module._assert_owns_vnc_port(admin_user.id, 6901)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_passes_for_the_owning_user_running_session(
        self, win_rom: Rom, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
                vnc_web_port=6901,
            )
        )
        install_module._assert_owns_vnc_port(admin_user.id, 6901)  # must not raise

    def test_raises_403_for_a_different_users_session(
        self, win_rom: Rom, editor_user: User, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=editor_user.id,
                state=InstallSessionState.INSTALLING,
                vnc_web_port=6901,
            )
        )
        with pytest.raises(HTTPException) as exc_info:
            install_module._assert_owns_vnc_port(admin_user.id, 6901)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


class TestInstallVncHttp:
    """The noVNC static-asset proxy (see install_vnc_http). The actual VNC
    pixel stream (install_vnc_ws) isn't covered here - a websocket-upgrade
    proxy isn't meaningfully testable through TestClient/aiohttp mocking
    without effectively re-testing aiohttp itself."""

    def test_port_with_no_matching_session_is_forbidden(
        self, client: TestClient, access_token: str
    ):
        r = client.get(
            "/api/roms/install/vnc/6901/vnc.html", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_403_FORBIDDEN

    def test_proxies_the_upstream_response_for_an_owned_session(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
                vnc_web_port=6901,
            )
        )

        class FakeContent:
            async def iter_any(self):
                yield b"<html>novnc</html>"

        fake_upstream = MagicMock()
        fake_upstream.status = 200
        fake_upstream.headers = {"X-Upstream": "novnc"}
        fake_upstream.content_type = "text/html"
        fake_upstream.content = FakeContent()
        fake_upstream.close = MagicMock()

        with patch(
            "aiohttp.ClientSession.request",
            new=AsyncMock(return_value=fake_upstream),
        ):
            r = client.get(
                "/api/roms/install/vnc/6901/vnc.html", headers=_auth(access_token)
            )

        assert r.status_code == status.HTTP_200_OK
        assert r.content == b"<html>novnc</html>"
        assert r.headers.get("x-upstream") == "novnc"

    def test_upstream_connection_failure_is_503(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
                vnc_web_port=6901,
            )
        )

        with patch(
            "aiohttp.ClientSession.request",
            new=AsyncMock(side_effect=aiohttp.ClientConnectionError()),
        ):
            r = client.get(
                "/api/roms/install/vnc/6901/vnc.html", headers=_auth(access_token)
            )

        assert r.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


class TestGetInstallFiles:
    def test_no_session_404s(self, client: TestClient, access_token: str, rom: Rom):
        r = client.get(f"/api/roms/{rom.id}/install/files", headers=_auth(access_token))
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_session_without_manifest_404s(
        self, client: TestClient, access_token: str, rom: Rom, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.STREAMING,
            )
        )
        r = client.get(f"/api/roms/{rom.id}/install/files", headers=_auth(access_token))
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_lists_manifest_files(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "game.exe").write_bytes(b"hello world")
        entries = build_manifest(cache_dir)
        write_manifest(cache_dir, entries)

        r = client.get(f"/api/roms/{rom.id}/install/files", headers=_auth(access_token))
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["total_bytes"] == 11
        assert body["files"] == [
            {"path": "game.exe", "size_bytes": 11, "sha1": entries[0].sha1}
        ]


class TestDownloadInstallFile:
    def test_unlisted_path_404s(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "game.exe").write_bytes(b"x")
        write_manifest(cache_dir, build_manifest(cache_dir))

        r = client.get(
            f"/api/roms/{rom.id}/install/files/not-in-the-manifest.exe",
            headers=_auth(access_token),
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_downloads_listed_file_in_dev_mode(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "game.exe").write_bytes(b"payload bytes")
        write_manifest(cache_dir, build_manifest(cache_dir))

        with patch("endpoints.roms.install.DEV_MODE", True):
            r = client.get(
                f"/api/roms/{rom.id}/install/files/game.exe",
                headers=_auth(access_token),
            )
        assert r.status_code == status.HTTP_200_OK
        assert r.content == b"payload bytes"


class TestDownloadInstallCache:
    def test_no_manifest_404s(
        self, client: TestClient, access_token: str, rom: Rom, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        r = client.get(
            f"/api/roms/{rom.id}/install/download", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_downloads_a_real_zip_in_dev_mode(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        cache_dir = install_cache_root / str(session.id)
        (cache_dir / "sub").mkdir(parents=True)
        (cache_dir / "game.exe").write_bytes(b"exe bytes")
        (cache_dir / "sub" / "data.bin").write_bytes(b"nested bytes")
        write_manifest(cache_dir, build_manifest(cache_dir))

        with patch("endpoints.roms.install.DEV_MODE", True):
            r = client.get(
                f"/api/roms/{rom.id}/install/download", headers=_auth(access_token)
            )
        assert r.status_code == status.HTTP_200_OK
        assert r.headers["content-type"] == "application/zip"
        assert "Install%20Cache.zip" in r.headers["content-disposition"]

        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            assert set(zf.namelist()) == {"game.exe", "sub/data.bin"}
            assert zf.read("game.exe") == b"exe bytes"
            assert zf.read("sub/data.bin") == b"nested bytes"

    def test_streams_via_mod_zip_in_production(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "game.exe").write_bytes(b"exe bytes")
        write_manifest(cache_dir, build_manifest(cache_dir))

        # DEV_MODE is False by default in tests - no nginx to intercept the
        # mod_zip headers, so this just checks the response is built
        # correctly, not that a real zip comes back (nginx never runs here).
        r = client.get(
            f"/api/roms/{rom.id}/install/download", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_200_OK
        assert r.headers["x-archive-files"] == "zip"
        assert f"/cache/installs/{session.id}/game.exe" in r.text


class TestGetInstallStreamManifest:
    def test_no_session_404s(self, client: TestClient, access_token: str, rom: Rom):
        r = client.get(
            f"/api/roms/{rom.id}/install/stream/manifest", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_reflects_the_live_manifest_while_still_installing(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        write_live_manifest(
            cache_dir,
            {
                "game.exe": LiveManifestEntry(
                    path="game.exe",
                    size_bytes=20,
                    sealed_bytes=8,
                    complete=False,
                )
            },
        )

        r = client.get(
            f"/api/roms/{rom.id}/install/stream/manifest", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["files"] == [
            {
                "path": "game.exe",
                "size_bytes": 20,
                "sealed_bytes": 8,
                "complete": False,
            }
        ]

    def test_falls_back_to_the_final_manifest_once_done(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "game.exe").write_bytes(b"hello world")
        write_manifest(cache_dir, build_manifest(cache_dir))

        r = client.get(
            f"/api/roms/{rom.id}/install/stream/manifest", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["files"] == [
            {
                "path": "game.exe",
                "size_bytes": 11,
                "sealed_bytes": 11,
                "complete": True,
            }
        ]

    def test_session_id_pins_to_that_session_even_when_a_newer_one_exists(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        # A finished attempt a client might still be streaming from...
        old_session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        old_cache_dir = install_cache_root / str(old_session.id)
        old_cache_dir.mkdir(parents=True)
        (old_cache_dir / "game.exe").write_bytes(b"hello world")
        write_manifest(old_cache_dir, build_manifest(old_cache_dir))

        # ...while a completely unrelated, fresh attempt starts for the same
        # ROM (a different client, or the same one pressing Install again) -
        # this becomes "latest" but must not steal a pinned client's view.
        new_session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
            )
        )
        new_cache_dir = install_cache_root / str(new_session.id)
        new_cache_dir.mkdir(parents=True)
        write_live_manifest(new_cache_dir, {})

        pinned = client.get(
            f"/api/roms/{rom.id}/install/stream/manifest?session_id={old_session.id}",
            headers=_auth(access_token),
        )
        assert pinned.status_code == status.HTTP_200_OK
        assert pinned.json()["files"] == [
            {
                "path": "game.exe",
                "size_bytes": 11,
                "sealed_bytes": 11,
                "complete": True,
            }
        ]

        # No session_id given still resolves to the latest (the new, still
        # empty session) as before - a client that never learned an id
        # keeps seeing whatever is currently the most recent attempt.
        unpinned = client.get(
            f"/api/roms/{rom.id}/install/stream/manifest", headers=_auth(access_token)
        )
        assert unpinned.status_code == status.HTTP_200_OK
        assert unpinned.json()["files"] == []

    def test_session_id_for_a_different_rom_404s(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        win_rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        other_session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.DONE,
            )
        )

        r = client.get(
            f"/api/roms/{rom.id}/install/stream/manifest?session_id={other_session.id}",
            headers=_auth(access_token),
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_reports_viewer_count_and_bandwidth_limit(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        write_live_manifest(cache_dir, {})

        await stream_presence.heartbeat(session.id, user_id=99, device_id="steamdeck")
        await bandwidth.set_bytes_per_second(500_000)
        try:
            r = client.get(
                f"/api/roms/{rom.id}/install/stream/manifest",
                headers=_auth(access_token),
            )
            assert r.status_code == status.HTTP_200_OK
            body = r.json()
            assert body["viewer_count"] == 1
            assert body["download_speed_limit_bytes_per_sec"] == 500_000
        finally:
            await bandwidth.set_bytes_per_second(None)


class TestDownloadInstallStreamFile:
    def test_unlisted_path_404s(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        write_live_manifest(cache_dir, {})

        r = client.get(
            f"/api/roms/{rom.id}/install/stream/not-tracked.exe",
            headers=_auth(access_token),
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND

    def test_serves_only_the_sealed_prefix_as_206(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "game.exe").write_bytes(b"0123456789ABCDEF")  # 16 bytes on disk
        write_live_manifest(
            cache_dir,
            {
                "game.exe": LiveManifestEntry(
                    path="game.exe",
                    size_bytes=16,
                    sealed_bytes=8,  # only the first 8 bytes are safe to read
                    complete=False,
                )
            },
        )

        r = client.get(
            f"/api/roms/{rom.id}/install/stream/game.exe", headers=_auth(access_token)
        )
        assert r.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert r.content == b"01234567"
        assert r.headers["content-range"] == "bytes 0-7/*"

    def test_range_past_sealed_bytes_is_416(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "game.exe").write_bytes(b"0123456789ABCDEF")
        write_live_manifest(
            cache_dir,
            {
                "game.exe": LiveManifestEntry(
                    path="game.exe",
                    size_bytes=16,
                    sealed_bytes=8,
                    complete=False,
                )
            },
        )

        r = client.get(
            f"/api/roms/{rom.id}/install/stream/game.exe",
            headers={**_auth(access_token), "Range": "bytes=10-15"},
        )
        assert r.status_code == status.HTTP_416_RANGE_NOT_SATISFIABLE

    def test_falls_through_to_the_finished_file_once_no_live_manifest_exists(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        admin_user: User,
        install_cache_root,
    ):
        session = db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        cache_dir = install_cache_root / str(session.id)
        cache_dir.mkdir(parents=True)
        (cache_dir / "game.exe").write_bytes(b"payload bytes")
        write_manifest(cache_dir, build_manifest(cache_dir))

        with patch("endpoints.roms.install.DEV_MODE", True):
            r = client.get(
                f"/api/roms/{rom.id}/install/stream/game.exe",
                headers=_auth(access_token),
            )
        assert r.status_code == status.HTTP_200_OK
        assert r.content == b"payload bytes"


class TestInstallDashboard:
    def test_empty_by_default(self, client: TestClient, access_token: str):
        r = client.get("/api/roms/install/dashboard", headers=_auth(access_token))
        assert r.status_code == status.HTTP_200_OK
        assert r.json() == {"entries": []}

    def test_includes_active_and_done_excludes_failed_and_expired(
        self, client: TestClient, access_token: str, rom: Rom, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
            )
        )
        r = client.get("/api/roms/install/dashboard", headers=_auth(access_token))
        assert r.status_code == status.HTTP_200_OK
        assert [e["rom_id"] for e in r.json()["entries"]] == [rom.id]

    def test_only_the_latest_session_per_rom_counts(
        self, client: TestClient, access_token: str, rom: Rom, admin_user: User
    ):
        # Older DONE session, newer FAILED one: the ROM shouldn't appear at
        # all, since only the latest session's state is looked at.
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=admin_user.id, state=InstallSessionState.FAILED
            )
        )
        r = client.get("/api/roms/install/dashboard", headers=_auth(access_token))
        assert r.json()["entries"] == []

    def test_entry_carries_rom_summary_fields(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id, user_id=admin_user.id, state=InstallSessionState.DONE
            )
        )
        r = client.get("/api/roms/install/dashboard", headers=_auth(access_token))
        entry = r.json()["entries"][0]
        assert entry["rom_id"] == win_rom.id
        assert entry["rom_name"] == win_rom.name
        assert entry["platform_slug"] == "win"
        assert entry["session"]["state"] == "done"

    def test_hides_other_users_sessions(
        self,
        client: TestClient,
        access_token: str,
        rom: Rom,
        editor_user: User,
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=rom.id, user_id=editor_user.id, state=InstallSessionState.DONE
            )
        )
        r = client.get("/api/roms/install/dashboard", headers=_auth(access_token))
        assert r.json()["entries"] == []


class TestSetInstallAutoMode:
    def test_toggles_the_flag_and_clears_the_status(
        self, client: TestClient, access_token: str, win_rom: Rom, admin_user: User
    ):
        db_install_session_handler.add_session(
            InstallSession(
                rom_id=win_rom.id,
                user_id=admin_user.id,
                state=InstallSessionState.INSTALLING,
                installer_path="setup.exe",
                auto_mode=True,
                auto_status="needs_manual",
                auto_detail="No known button on screen",
            )
        )
        r = client.patch(
            f"/api/roms/{win_rom.id}/install/auto-mode",
            json={"enabled": False},
            headers=_auth(access_token),
        )
        assert r.status_code == status.HTTP_200_OK
        body = r.json()
        assert body["auto_mode"] is False
        assert body["auto_status"] is None
        assert body["auto_detail"] is None

    def test_missing_session_404s(
        self, client: TestClient, access_token: str, win_rom: Rom
    ):
        r = client.patch(
            f"/api/roms/{win_rom.id}/install/auto-mode",
            json={"enabled": True},
            headers=_auth(access_token),
        )
        assert r.status_code == status.HTTP_404_NOT_FOUND
