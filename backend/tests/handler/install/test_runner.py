import subprocess
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import handler.install.runner as runner
from handler.install.manifest import LiveManifestEntry


class TestUsesWine:
    def test_true_for_a_windows_installer(self):
        assert runner._uses_wine("/library/win/game/setup.exe") is True

    @pytest.mark.parametrize("ext", [".sh", ".run", ".SH", ".RUN"])
    def test_false_for_native_linux_installers(self, ext):
        assert runner._uses_wine(f"/library/linux/game/install{ext}") is False


class TestWineOrProton:
    def test_defaults_to_wine_when_no_builds_installed(self, monkeypatch):
        monkeypatch.setattr(runner, "resolve_proton_path", lambda _: None)
        monkeypatch.setattr(runner, "list_proton_builds", lambda: [])
        assert runner._wine_or_proton() == "wine"

    def test_uses_resolved_proton_path(self, monkeypatch):
        monkeypatch.setattr(
            runner, "resolve_proton_path", lambda _: "/opt/proton/GE-Proton10-34/proton"
        )
        assert runner._wine_or_proton("GE-Proton10-34") == "/opt/proton/GE-Proton10-34/proton"

    def test_unset_proton_build_falls_back_to_first_installed(self, monkeypatch):
        from handler.install.proton_builds import ProtonBuild

        monkeypatch.setattr(runner, "resolve_proton_path", lambda _: None)
        monkeypatch.setattr(
            runner,
            "list_proton_builds",
            lambda: [
                ProtonBuild(
                    id="GE-Proton10-34",
                    label="GE-Proton 10-34",
                    installed=True,
                    path="/opt/proton/GE-Proton10-34/proton",
                ),
                ProtonBuild(
                    id="cachyos-latest",
                    label="Proton-CachyOS",
                    installed=True,
                    path="/opt/proton/cachyos-latest/proton",
                ),
            ],
        )
        # With proton_build=None, falls back to the first installed build.
        assert runner._wine_or_proton(None) == "/opt/proton/GE-Proton10-34/proton"

    def test_unknown_proton_build_falls_back_to_first_installed(
        self, monkeypatch
    ):
        from handler.install.proton_builds import ProtonBuild

        monkeypatch.setattr(runner, "resolve_proton_path", lambda _: None)
        monkeypatch.setattr(
            runner,
            "list_proton_builds",
            lambda: [
                ProtonBuild(
                    id="GE-Proton10-34",
                    label="GE-Proton 10-34",
                    installed=True,
                    path="/opt/proton/GE-Proton10-34/proton",
                ),
            ],
        )
        assert runner._wine_or_proton("not-a-real-build") == "/opt/proton/GE-Proton10-34/proton"

    def test_recognized_proton_build_resolves_via_the_registry(self, monkeypatch):
        monkeypatch.setattr(
            runner, "resolve_proton_path", lambda build_id: "/opt/proton/other/proton"
        )
        assert runner._wine_or_proton("some-build") == "/opt/proton/other/proton"


class TestIsProton:
    def test_true_for_a_path_named_proton(self):
        assert runner._is_proton("/opt/proton/proton") is True

    def test_false_for_plain_wine(self):
        assert runner._is_proton("wine") is False

    def test_false_for_a_differently_named_wine_build(self):
        assert runner._is_proton("/opt/lutris/wine-ge/bin/wine") is False


class TestWineDriveCRoot:
    def test_proton_nests_under_pfx(self):
        assert runner._wine_drive_c_root(
            Path("/cache/1/prefix"), "/opt/proton/proton"
        ) == Path("/cache/1/prefix/pfx")

    def test_plain_wine_uses_the_prefix_directly(self):
        assert runner._wine_drive_c_root(Path("/cache/1/prefix"), "wine") == Path(
            "/cache/1/prefix"
        )


class TestBuildInnerCommand:
    def test_wraps_windows_installer_with_wine(self):
        assert runner._build_inner_command("/library/win/game/setup.exe", "wine") == [
            "wine",
            "/library/win/game/setup.exe",
        ]

    def test_wraps_windows_installer_with_proton_waitforexitandrun(self):
        # Not "run": protonfixes.execute() only applies Proton's own
        # per-game/per-installer compatibility fixes for this verb.
        assert runner._build_inner_command(
            "/library/win/game/setup.exe", "/opt/proton/proton"
        ) == ["/opt/proton/proton", "waitforexitandrun", "/library/win/game/setup.exe"]

    def test_runs_native_installers_directly_through_sh_even_with_proton(self):
        # .sh/.run installers never touch Wine/Proton regardless of what's
        # configured - _uses_wine gates this before proton_or_wine matters.
        assert runner._build_inner_command(
            "/library/linux/game/install.sh", "/opt/proton/proton"
        ) == ["/bin/sh", "/library/linux/game/install.sh"]


class TestWrapForSandbox:
    """bwrap only exposes what's explicitly bound in. Now only the resolved
    Proton build's own directory is bound (not all env-var paths), and only
    if it actually exists — guarding against the bwrap crash when a stale
    env var points at a non-existent path."""

    def _captured_ro_binds(self, monkeypatch) -> list[tuple[str, ...]]:
        captured: list[tuple[str, ...]] = []
        monkeypatch.setattr(
            runner,
            "build_bwrap_command",
            lambda spec, inner: captured.append(spec.ro_binds) or inner,
        )
        return captured

    def test_binds_only_the_resolved_proton_builds_directory(
        self, monkeypatch, tmp_path
    ):
        captured = self._captured_ro_binds(monkeypatch)
        proton_dir = tmp_path / "GE-Proton10-34"
        proton_dir.mkdir()
        proton_bin = proton_dir / "proton"
        proton_bin.write_text("")

        runner._wrap_for_sandbox(
            ["true"],
            installer_abs="/library/win/game/setup.exe",
            work_dir="/work",
            proton_prefix="/prefix",
            display=":50",
            proton_or_wine=str(proton_bin),
        )

        # Only the selected build's directory is bound, not all possible ones.
        assert captured[0] == (str(proton_dir),)

    def test_binds_nothing_for_plain_wine(self, monkeypatch):
        captured = self._captured_ro_binds(monkeypatch)

        runner._wrap_for_sandbox(
            ["true"],
            installer_abs="/library/win/game/setup.exe",
            work_dir="/work",
            proton_prefix="/prefix",
            display=":50",
            proton_or_wine="wine",
        )

        # Plain Wine lives under /usr which is already ro-bound by the
        # sandbox spec; no extra ro_bind is needed.
        assert captured[0] == ()

    def test_binds_nothing_when_proton_path_doesnt_exist(self, monkeypatch):
        # The crash fix: a stale/non-existent path must not attempt a bwrap
        # bind (which fails with "Can't find source path"), just skip it.
        captured = self._captured_ro_binds(monkeypatch)

        runner._wrap_for_sandbox(
            ["true"],
            installer_abs="/library/win/game/setup.exe",
            work_dir="/work",
            proton_prefix="/prefix",
            display=":50",
            proton_or_wine="/opt/proton/GE-Proton10-34/proton",
        )
        # Path doesn't exist on the test machine, so no ro_bind is set.
        assert captured[0] == ()

    def test_binds_installer_search_root_when_it_exists(self, monkeypatch, tmp_path):
        # Sibling data files (setup-N.bin, Data1.cab, ...) live next to the
        # installer for multi-part InstallShield-based installers -
        # ISArcExtract needs the whole containing directory visible, not
        # just the one file SandboxSpec always binds on its own.
        captured = self._captured_ro_binds(monkeypatch)

        runner._wrap_for_sandbox(
            ["true"],
            installer_abs=str(tmp_path / "setup.exe"),
            work_dir="/work",
            proton_prefix="/prefix",
            display=":50",
            proton_or_wine="wine",
            installer_search_root=str(tmp_path),
        )

        assert captured[0] == (str(tmp_path),)

    def test_skips_installer_search_root_when_it_doesnt_exist(self, monkeypatch):
        captured = self._captured_ro_binds(monkeypatch)

        runner._wrap_for_sandbox(
            ["true"],
            installer_abs="/library/win/game/setup.exe",
            work_dir="/work",
            proton_prefix="/prefix",
            display=":50",
            proton_or_wine="wine",
            installer_search_root="/does/not/exist",
        )

        assert captured[0] == ()

    def test_combines_proton_and_installer_search_root_binds(
        self, monkeypatch, tmp_path
    ):
        captured = self._captured_ro_binds(monkeypatch)
        proton_dir = tmp_path / "proton_build"
        proton_dir.mkdir()
        proton_bin = proton_dir / "proton"
        proton_bin.write_text("")
        installer_dir = tmp_path / "game"
        installer_dir.mkdir()

        runner._wrap_for_sandbox(
            ["true"],
            installer_abs=str(installer_dir / "setup.exe"),
            work_dir="/work",
            proton_prefix="/prefix",
            display=":50",
            proton_or_wine=str(proton_bin),
            installer_search_root=str(installer_dir),
        )

        assert captured[0] == (str(proton_dir), str(installer_dir))

    def test_sandbox_disabled_skips_bwrap_entirely(self, monkeypatch):
        monkeypatch.setattr(runner, "INSTALL_SANDBOX_ENABLED", False)
        result = runner._wrap_for_sandbox(
            ["true"],
            installer_abs="/library/win/game/setup.exe",
            work_dir="/work",
            proton_prefix="/prefix",
            display=":50",
            proton_or_wine="wine",
        )
        assert result == ["true"]


class TestInitWinePrefix:
    def test_runs_wineboot_init_wrapped_in_the_sandbox(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            runner, "_wrap_for_sandbox", lambda inner, **kw: ["bwrap", "--", *inner]
        )
        monkeypatch.setattr(
            runner.subprocess,
            "run",
            lambda argv, **kw: calls.append((argv, kw)),
        )

        runner._init_wine_prefix(
            "wine",
            installer_abs="/library/win/game/setup.exe",
            work_dir="/cache/1",
            prefix_dir="/cache/1/prefix",
            display=":99",
        )

        argv, kwargs = calls[0]
        assert argv == ["bwrap", "--", "wine", "wineboot", "--init"]
        assert kwargs["timeout"] == runner.WINE_PREFIX_INIT_TIMEOUT
        assert kwargs["check"] is True

    def test_runs_wineboot_init_through_proton_run(self, monkeypatch):
        wrapped = []
        monkeypatch.setattr(
            runner,
            "_wrap_for_sandbox",
            lambda inner, **kw: (wrapped.append((inner, kw)), ["bwrap", "--", *inner])[
                1
            ],
        )
        monkeypatch.setattr(runner.subprocess, "run", lambda argv, **kw: None)

        runner._init_wine_prefix(
            "/opt/proton/proton",
            installer_abs="/library/win/game/setup.exe",
            work_dir="/cache/1",
            prefix_dir="/cache/1/prefix",
            display=":99",
            extra_env=(("STEAM_COMPAT_DATA_PATH", "/cache/1/prefix"),),
        )

        inner, kwargs = wrapped[0]
        assert inner == ["/opt/proton/proton", "run", "wineboot", "--init"]
        assert kwargs["extra_env"] == (("STEAM_COMPAT_DATA_PATH", "/cache/1/prefix"),)

    def test_retries_once_and_succeeds_on_a_transient_failure(self, monkeypatch):
        monkeypatch.setattr(runner, "_wrap_for_sandbox", lambda inner, **kw: inner)
        sleeps = []
        monkeypatch.setattr(runner.time, "sleep", sleeps.append)

        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            if len(calls) == 1:
                raise subprocess.CalledProcessError(
                    returncode=53, cmd=argv, stderr=b"transient X race"
                )

        monkeypatch.setattr(runner.subprocess, "run", fake_run)

        runner._init_wine_prefix(
            "wine",
            installer_abs="/library/win/game/setup.exe",
            work_dir="/cache/1",
            prefix_dir="/cache/1/prefix",
            display=":99",
        )  # must not raise

        assert len(calls) == 2
        assert sleeps == [runner.WINE_PREFIX_INIT_RETRY_DELAY]

    def test_raises_a_clear_error_including_stderr_after_all_attempts_fail(
        self, monkeypatch
    ):
        monkeypatch.setattr(runner, "_wrap_for_sandbox", lambda inner, **kw: inner)
        monkeypatch.setattr(runner.time, "sleep", lambda s: None)

        def fake_run(argv, **kwargs):
            raise subprocess.CalledProcessError(
                returncode=53, cmd=argv, stderr=b"kernel32.dll not found"
            )

        monkeypatch.setattr(runner.subprocess, "run", fake_run)

        with pytest.raises(
            RuntimeError, match="Failed to initialize the Wine prefix.*kernel32"
        ):
            runner._init_wine_prefix(
                "wine",
                installer_abs="/library/win/game/setup.exe",
                work_dir="/cache/1",
                prefix_dir="/cache/1/prefix",
                display=":99",
            )

    def test_error_label_says_proton_when_using_proton(self, monkeypatch):
        monkeypatch.setattr(runner, "_wrap_for_sandbox", lambda inner, **kw: inner)
        monkeypatch.setattr(runner.time, "sleep", lambda s: None)

        def fake_run(argv, **kwargs):
            raise subprocess.CalledProcessError(returncode=1, cmd=argv, stderr=b"")

        monkeypatch.setattr(runner.subprocess, "run", fake_run)

        with pytest.raises(
            RuntimeError, match="Failed to initialize the Proton prefix"
        ):
            runner._init_wine_prefix(
                "/opt/proton/proton",
                installer_abs="/library/win/game/setup.exe",
                work_dir="/cache/1",
                prefix_dir="/cache/1/prefix",
                display=":99",
            )

    def test_raises_a_clear_error_on_timeout(self, monkeypatch):
        monkeypatch.setattr(runner, "_wrap_for_sandbox", lambda inner, **kw: inner)
        monkeypatch.setattr(runner.time, "sleep", lambda s: None)

        def fake_run(argv, **kwargs):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))

        monkeypatch.setattr(runner.subprocess, "run", fake_run)

        with pytest.raises(
            RuntimeError, match="Timed out initializing the Wine prefix"
        ):
            runner._init_wine_prefix(
                "wine",
                installer_abs="/library/win/game/setup.exe",
                work_dir="/cache/1",
                prefix_dir="/cache/1/prefix",
                display=":99",
            )


class TestFocusMaintenanceLoop:
    def test_focuses_immediately_then_on_every_interval(self, monkeypatch):
        monkeypatch.setattr(runner, "FOCUS_MAINTENANCE_INTERVAL", 0)

        focus_calls: list[dict] = []
        stop = threading.Event()

        def fake_focus(env, state):
            focus_calls.append(env)
            if len(focus_calls) >= 3:
                stop.set()

        monkeypatch.setattr(runner, "_focus_installer_window", fake_focus)

        runner._focus_maintenance_loop(":99", stop)

        assert len(focus_calls) == 3
        assert all(env["DISPLAY"] == ":99" for env in focus_calls)

    def test_passes_the_same_state_across_every_call(self, monkeypatch):
        # A fresh _FocusState per loop invocation (one per install run), but
        # the *same* instance threaded through every tick within that run -
        # otherwise "new window" detection could never work (everything
        # would look new every time).
        monkeypatch.setattr(runner, "FOCUS_MAINTENANCE_INTERVAL", 0)

        states: list[runner._FocusState] = []
        stop = threading.Event()

        def fake_focus(env, state):
            states.append(state)
            if len(states) >= 3:
                stop.set()

        monkeypatch.setattr(runner, "_focus_installer_window", fake_focus)

        runner._focus_maintenance_loop(":99", stop)

        assert len(states) == 3
        assert states[0] is states[1] is states[2]

    def test_never_sends_any_key(self, monkeypatch):
        # This loop only ever grabs focus - it must never type or click on
        # the user's behalf; they drive the installer through VNC themselves.
        monkeypatch.setattr(runner, "FOCUS_MAINTENANCE_INTERVAL", 0)
        monkeypatch.setattr(runner, "_focus_installer_window", lambda env, state: None)

        key_calls = []
        monkeypatch.setattr(
            runner.subprocess,
            "run",
            lambda argv, **kw: key_calls.append(argv),
        )

        stop = threading.Event()
        stop.set()
        runner._focus_maintenance_loop(":99", stop)

        assert key_calls == []

    def test_stops_promptly_when_signalled(self, monkeypatch):
        focus_calls: list[dict] = []
        monkeypatch.setattr(
            runner,
            "_focus_installer_window",
            lambda env, state: focus_calls.append(env),
        )

        stop = threading.Event()
        stop.set()
        runner._focus_maintenance_loop(":99", stop)

        # The immediate focus call still happens once before the loop checks
        # `stop`, but nothing after.
        assert len(focus_calls) == 1


class TestFocusInstallerWindow:
    def _fake_run(self, window_names: dict[str, tuple[str, str]]):
        """window_names: {window_id: (name, "WIDTHxHEIGHT")}."""
        calls: list[list[str]] = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            out = MagicMock()
            if argv[1] == "search":
                out.stdout = " ".join(window_names.keys())
            elif argv[1] == "getwindowname":
                out.stdout = window_names[argv[-1]][0]
            elif argv[1] == "getwindowgeometry":
                w, h = window_names[argv[-1]][1].split("x")
                out.stdout = f"WIDTH={w}\nHEIGHT={h}\n"
            else:
                out.stdout = ""
            return out

        return fake_run, calls

    def test_focuses_the_largest_non_chrome_window_on_first_check(
        self, monkeypatch
    ):
        # Nothing has been seen yet, so every non-chrome candidate is
        # technically "new" - with only one real candidate, that's
        # indistinguishable from the old largest-area behaviour.
        fake_run, calls = self._fake_run(
            {
                "1": ("IceTopWin", "1x1"),
                "2": ("Select Setup Language", "297x125"),
                "3": ("Default IME", "1x1"),
                # IceWM's own per-window decoration wrapper - same name for
                # every managed window, including the real one above. Its
                # geometry can tie or beat the client's; must still lose.
                "4": ("Frame", "301x148"),
            }
        )
        monkeypatch.setattr(runner.subprocess, "run", fake_run)

        runner._focus_installer_window({"DISPLAY": ":99"}, runner._FocusState())

        focus_call = next(c for c in calls if c[1] == "windowfocus")
        assert focus_call == ["xdotool", "windowfocus", "--sync", "2"]

    def test_does_nothing_when_only_chrome_windows_exist(self, monkeypatch):
        fake_run, calls = self._fake_run(
            {"1": ("IceTopWin", "1x1"), "2": ("IceBottom", "1x1")}
        )
        monkeypatch.setattr(runner.subprocess, "run", fake_run)

        runner._focus_installer_window({"DISPLAY": ":99"}, runner._FocusState())

        assert not any(c[1] == "windowfocus" for c in calls)

    def test_swallows_missing_binary(self, monkeypatch):
        def fake_run(argv, **kwargs):
            raise FileNotFoundError("xdotool not installed")

        monkeypatch.setattr(runner.subprocess, "run", fake_run)

        # Must not raise: a missing/misbehaving xdotool shouldn't crash the install.
        runner._focus_installer_window({"DISPLAY": ":99"}, runner._FocusState())

    def test_a_new_small_window_wins_over_a_bigger_already_seen_one(
        self, monkeypatch
    ):
        # The actual bug this loop used to have: a big window (e.g. a
        # progress/splash dialog) is already on screen and already seen,
        # then a small dialog needing immediate keyboard input (e.g. "press
        # Up to dismiss") pops up. Picking by size alone would keep the big
        # window focused forever; the newly-appeared small one must win.
        state = runner._FocusState()
        fake_run, _ = self._fake_run({"10": ("Big Splash", "800x600")})
        monkeypatch.setattr(runner.subprocess, "run", fake_run)
        runner._focus_installer_window({"DISPLAY": ":99"}, state)
        assert state.target == "10"

        fake_run2, calls2 = self._fake_run(
            {
                "10": ("Big Splash", "800x600"),
                "11": ("Select Setup Language", "297x125"),
            }
        )
        monkeypatch.setattr(runner.subprocess, "run", fake_run2)
        runner._focus_installer_window({"DISPLAY": ":99"}, state)

        focus_call = next(c for c in calls2 if c[1] == "windowfocus")
        assert focus_call == ["xdotool", "windowfocus", "--sync", "11"]
        assert state.target == "11"

    def test_stays_on_target_across_ticks_instead_of_reverting_to_the_bigger_window(
        self, monkeypatch
    ):
        # This is the part the naive "prefer new, else largest" version
        # would get wrong: on the tick *after* the small window won, it's no
        # longer "new" - without a sticky target, largest-area would pick
        # the big window right back, undoing the fix a second later.
        state = runner._FocusState()
        both = {
            "10": ("Big Splash", "800x600"),
            "11": ("Select Setup Language", "297x125"),
        }
        fake_run, _ = self._fake_run(both)
        monkeypatch.setattr(runner.subprocess, "run", fake_run)
        runner._focus_installer_window({"DISPLAY": ":99"}, state)  # "10" is new
        runner._focus_installer_window({"DISPLAY": ":99"}, state)  # "11" is new
        assert state.target == "11"

        fake_run2, calls2 = self._fake_run(both)  # nothing new this tick
        monkeypatch.setattr(runner.subprocess, "run", fake_run2)
        runner._focus_installer_window({"DISPLAY": ":99"}, state)

        focus_call = next(c for c in calls2 if c[1] == "windowfocus")
        assert focus_call == ["xdotool", "windowfocus", "--sync", "11"]

    def test_falls_back_to_largest_when_the_target_disappears(self, monkeypatch):
        state = runner._FocusState(seen_ids={"10", "11"}, target="11")
        # "11" (the previous target) is gone; only "10" remains, and it's
        # already in seen_ids so it isn't "new" either.
        fake_run, calls = self._fake_run({"10": ("Big Splash", "800x600")})
        monkeypatch.setattr(runner.subprocess, "run", fake_run)

        runner._focus_installer_window({"DISPLAY": ":99"}, state)

        focus_call = next(c for c in calls if c[1] == "windowfocus")
        assert focus_call == ["xdotool", "windowfocus", "--sync", "10"]
        assert state.target == "10"


class TestRunInstaller:
    def test_waits_for_process_and_stops_focus_loop(self, monkeypatch):
        events: list[str] = []

        class FakeProc:
            def wait(self, timeout=None):
                events.append("wait")
                return 0

        monkeypatch.setattr(
            runner.subprocess,
            "Popen",
            lambda argv: (events.append(("popen", argv)), FakeProc())[1],
        )

        stopped_with: list[str] = []

        def fake_loop(display, stop):
            stop.wait(2)
            stopped_with.append(display)

        monkeypatch.setattr(runner, "_focus_maintenance_loop", fake_loop)

        runner._run_installer(["true"], ":50")

        assert events[0] == ("popen", ["true"])
        assert "wait" in events
        assert stopped_with == [":50"]

    def test_kills_process_and_reraises_on_timeout(self, monkeypatch):
        class FakeProc:
            def __init__(self):
                self.wait_calls = 0
                self.killed = False

            def wait(self, timeout=None):
                self.wait_calls += 1
                if self.wait_calls == 1:
                    raise subprocess.TimeoutExpired(cmd="installer", timeout=timeout)
                return 0

            def kill(self):
                self.killed = True

        fake = FakeProc()
        monkeypatch.setattr(runner.subprocess, "Popen", lambda argv: fake)
        monkeypatch.setattr(
            runner, "_focus_maintenance_loop", lambda display, stop: stop.wait(2)
        )

        with pytest.raises(subprocess.TimeoutExpired):
            runner._run_installer(["true"], ":50")

        assert fake.killed is True
        assert fake.wait_calls == 2


class TestInstallOutputLooksFinished:
    """Regression coverage for a real bug: an install whose actual file
    output was 100% complete (all 436 files, including the uninstaller
    InnoSetup writes as its literal last step) got discarded as a plain
    failure because the sandbox process itself never exited within the
    hour-long INSTALL_TIMEOUT - almost certainly because nobody was
    watching to click the installer's own final "Finish" dialog. See
    run_install's own use of this function for where the salvage
    decision actually happens."""

    def test_true_when_every_tracked_file_is_fully_sealed(self, tmp_path):
        from handler.install.manifest import write_live_manifest

        write_live_manifest(
            tmp_path,
            {
                "a.exe": LiveManifestEntry(
                    path="a.exe", size_bytes=100, sealed_bytes=100, complete=False
                ),
                "b.dll": LiveManifestEntry(
                    path="b.dll", size_bytes=50, sealed_bytes=50, complete=False
                ),
            },
        )
        assert runner._install_output_looks_finished(tmp_path) is True

    def test_false_when_a_file_is_still_mid_write(self, tmp_path):
        from handler.install.manifest import write_live_manifest

        write_live_manifest(
            tmp_path,
            {
                "a.exe": LiveManifestEntry(
                    path="a.exe", size_bytes=100, sealed_bytes=100, complete=False
                ),
                "b.dll": LiveManifestEntry(
                    # Still growing - not yet sealed up to its current size.
                    path="b.dll", size_bytes=500, sealed_bytes=50, complete=False
                ),
            },
        )
        assert runner._install_output_looks_finished(tmp_path) is False

    def test_false_when_no_live_manifest_was_ever_written(self, tmp_path):
        # Native (non-Wine) installers never start the live-manifest loop
        # at all, or the installer crashed before writing anything.
        assert runner._install_output_looks_finished(tmp_path) is False


class TestFinalizeInstall:
    """Regression coverage for a real bug: the installer's actual output
    lives several levels deep inside the Wine prefix
    (`prefix/pfx/drive_c/...`), but every manifest path - and the download
    endpoint that serves it - is relative to the session's own cache
    directory (`work_dir`), per `handler.install.manifest`'s own module
    docstring. `_finalize_install` used to hash files in place and record
    them relative to the (deeply nested, vendor-folder-trimmed) discovery
    root without ever moving them, so `work_dir / entry.path` - exactly what
    the download endpoints resolve - pointed at a path that was never real
    on disk. Caught live: a finished install (state=done) 500'd on every
    file download with "File at path ... does not exist."
    """

    def _setup(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            runner, "db_install_session_handler", MagicMock()
        )
        work_dir = tmp_path / "work"
        prefix_dir = work_dir / "prefix"
        drive_c = prefix_dir / "drive_c"
        drive_c.mkdir(parents=True)
        work_dir.mkdir(exist_ok=True)
        return work_dir, prefix_dir, drive_c

    def test_relocates_a_single_vendor_folder_install_under_work_dir(
        self, tmp_path, monkeypatch
    ):
        work_dir, prefix_dir, drive_c = self._setup(tmp_path, monkeypatch)
        game_file = drive_c / "GOG Games" / "Some Game" / "data.bin"
        game_file.parent.mkdir(parents=True)
        game_file.write_bytes(b"payload")

        runner._finalize_install(1, prefix_dir, work_dir)

        # The vendor folder is trimmed from the exposed path (resolve_install_root),
        # and the file itself must have actually moved there - not just been
        # recorded as if it had.
        moved = work_dir / "Some Game" / "data.bin"
        assert moved.is_file()
        assert moved.read_bytes() == b"payload"
        assert not game_file.exists()

        from handler.install.manifest import read_manifest

        entries = read_manifest(work_dir)
        assert entries is not None
        assert len(entries) == 1
        assert entries[0].path == "Some Game/data.bin"
        # The exact join the download endpoint performs - must resolve.
        assert (work_dir / entries[0].path).is_file()

    def test_relocates_an_ambiguous_root_install_under_work_dir(
        self, tmp_path, monkeypatch
    ):
        # Two top-level content folders under drive_c (e.g. a vendor folder
        # plus a Wine user-profile shortcut) make resolve_install_root fall
        # back to drive_c itself, untrimmed - the exact shape of the live
        # session (163) that surfaced this bug. Even then, every manifest
        # path must still resolve under work_dir once finalized.
        work_dir, prefix_dir, drive_c = self._setup(tmp_path, monkeypatch)
        game_file = drive_c / "GOG Games" / "Some Game" / "data.bin"
        game_file.parent.mkdir(parents=True)
        game_file.write_bytes(b"payload")
        shortcut = drive_c / "users" / "steamuser" / "Desktop" / "Some Game.lnk"
        shortcut.parent.mkdir(parents=True)
        shortcut.write_bytes(b"lnk")

        runner._finalize_install(1, prefix_dir, work_dir)

        from handler.install.manifest import read_manifest

        entries = read_manifest(work_dir)
        assert entries is not None
        assert {e.path for e in entries} == {
            "GOG Games/Some Game/data.bin",
            "users/steamuser/Desktop/Some Game.lnk",
        }
        for entry in entries:
            assert (work_dir / entry.path).is_file()
        assert not game_file.exists()
        assert not shortcut.exists()

    def test_raises_when_nothing_was_found(self, tmp_path, monkeypatch):
        work_dir, prefix_dir, _drive_c = self._setup(tmp_path, monkeypatch)

        with pytest.raises(RuntimeError, match="no files were found"):
            runner._finalize_install(1, prefix_dir, work_dir)


class TestLiveManifestLoop:
    """Regression coverage for a real bug: while an install was still
    running, its live manifest recorded paths relative to the (deeply
    nested) discovery root - exactly the same contract violation
    TestFinalizeInstall covers for the finished-install case - so the
    download endpoint (which always resolves against `work_dir`) could
    never actually find a file mid-install, no matter how long the user
    watched it "stream". Caught live: a real install with a real growing
    UnityPlayer.dll on disk, 500ing on every attempt to download it."""

    def _setup(self, tmp_path):
        work_dir = tmp_path / "work"
        prefix_dir = work_dir / "prefix"
        drive_c = prefix_dir / "drive_c"
        drive_c.mkdir(parents=True)
        work_dir.mkdir(exist_ok=True)
        return work_dir, prefix_dir, drive_c

    def test_hardlinks_a_new_file_into_work_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(runner, "LIVE_MANIFEST_INTERVAL", 0)
        work_dir, prefix_dir, drive_c = self._setup(tmp_path)
        game_file = drive_c / "GOG Games" / "Some Game" / "data.bin"
        game_file.parent.mkdir(parents=True)
        game_file.write_bytes(b"partial")

        stop = threading.Event()
        stop.set()  # run exactly one iteration
        runner._live_manifest_loop(work_dir, prefix_dir, frozenset(), stop)

        # The exact join the download endpoint performs - must resolve, and
        # must be the real, growable file (a hardlink), not a snapshot copy.
        linked = work_dir / "Some Game" / "data.bin"
        assert linked.is_file()
        assert linked.read_bytes() == b"partial"
        assert linked.stat().st_ino == game_file.stat().st_ino
        # The original is left alone - _finalize_install's own separate,
        # move-based pass still needs to find it once the installer exits.
        assert game_file.exists()

        from handler.install.manifest import read_live_manifest

        live = read_live_manifest(work_dir)
        assert live is not None
        assert "Some Game/data.bin" in live

    def test_a_file_keeps_growing_at_its_hardlinked_path_across_scans(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(runner, "LIVE_MANIFEST_INTERVAL", 0)
        work_dir, prefix_dir, drive_c = self._setup(tmp_path)
        game_file = drive_c / "Some Game" / "data.bin"
        game_file.parent.mkdir(parents=True)
        game_file.write_bytes(b"a" * 100)

        stop = threading.Event()
        scans = []
        real_collect = runner.collect_windows_install_files

        def fake_collect(prefix, baseline):
            scans.append(1)
            if len(scans) == 2:
                # The installer wrote more between the two scans.
                game_file.write_bytes(b"a" * 200)
            if len(scans) >= 2:
                stop.set()
            return real_collect(prefix, baseline)

        monkeypatch.setattr(runner, "collect_windows_install_files", fake_collect)
        runner._live_manifest_loop(work_dir, prefix_dir, frozenset(), stop)

        linked = work_dir / "Some Game" / "data.bin"
        # Same hardlinked path throughout - the growth must show up there,
        # not get lost because a later scan re-resolved a different path.
        assert linked.stat().st_size == 200
        assert len(scans) == 2

    def test_finalize_still_finds_the_original_after_the_live_loop_linked_it(
        self, tmp_path, monkeypatch
    ):
        # The scenario TestFinalizeInstall alone can't cover: a file the
        # live loop already hardlinked into work_dir mid-install must not
        # confuse _finalize_install's own, independent, move-based pass
        # once the installer exits - same-inode "move onto itself" must be
        # harmless, and the file must still end up correctly in the final
        # manifest.
        monkeypatch.setattr(runner, "LIVE_MANIFEST_INTERVAL", 0)
        monkeypatch.setattr(runner, "db_install_session_handler", MagicMock())
        work_dir, prefix_dir, drive_c = self._setup(tmp_path)
        game_file = drive_c / "Some Game" / "data.bin"
        game_file.parent.mkdir(parents=True)
        game_file.write_bytes(b"final content")

        stop = threading.Event()
        stop.set()
        runner._live_manifest_loop(work_dir, prefix_dir, frozenset(), stop)
        assert (work_dir / "Some Game" / "data.bin").is_file()

        runner._finalize_install(1, prefix_dir, work_dir)

        from handler.install.manifest import read_manifest

        entries = read_manifest(work_dir)
        assert entries is not None
        assert len(entries) == 1
        assert entries[0].path == "Some Game/data.bin"
        assert (work_dir / entries[0].path).read_bytes() == b"final content"


class TestRunInstallerAutoMode:
    def test_auto_mode_thread_starts_only_when_a_session_is_given(self, monkeypatch, tmp_path):
        started = []

        class FakeProc:
            def wait(self, timeout=None):
                return 0

        monkeypatch.setattr(runner.subprocess, "Popen", lambda argv: FakeProc())
        monkeypatch.setattr(
            runner, "_focus_maintenance_loop", lambda display, stop: None
        )

        def fake_start(session_id, display, work_dir, stop):
            started.append((session_id, display, work_dir))
            thread = runner.threading.Thread(target=lambda: None)
            thread.start()
            return thread

        monkeypatch.setattr(runner, "start_auto_mode", fake_start)

        runner._run_installer(["true"], ":50")
        assert started == []

        runner._run_installer(["true"], ":50", auto_mode_session=(7, tmp_path))
        assert started == [(7, ":50", tmp_path)]


class TestNotifyInstallEnd:
    """`run_install` notifies the session's owner exactly once, from the
    final DB state - regardless of which internal `_fail`/`_finalize_install`
    call site got there, since none of them know about notifications."""

    def _session(self, state, **overrides):
        fields = {"user_id": 42, "rom_id": 7, "error": None, **overrides}
        return MagicMock(state=state, **fields)

    def _rom(self, name="Olden Era", fs_name="olden-era"):
        # MagicMock reserves the "name" kwarg for its own repr, not an
        # attribute - it has to be set afterwards.
        rom = MagicMock(fs_name=fs_name)
        rom.name = name
        return rom

    def test_done_notifies_success(self, monkeypatch):
        from models.install_session import InstallSessionState
        from models.notification import NotificationKind, NotificationLevel

        session_handler = MagicMock()
        session_handler.get_session.return_value = self._session(
            InstallSessionState.DONE
        )
        monkeypatch.setattr(runner, "db_install_session_handler", session_handler)
        monkeypatch.setattr(
            runner,
            "db_rom_handler",
            MagicMock(get_rom_visibility_label=lambda _id: self._rom()),
        )
        notify = AsyncMock()
        monkeypatch.setattr("handler.notification_handler.notify", notify)

        runner._notify_install_end(1)

        notify.assert_awaited_once()
        args, _ = notify.await_args
        assert args[0] == 42
        assert args[1] == NotificationKind.INSTALL_COMPLETED
        assert args[2] == NotificationLevel.SUCCESS
        assert args[3]["rom_name"] == "Olden Era"

    def test_failed_notifies_failure_with_the_error(self, monkeypatch):
        from models.install_session import InstallSessionState
        from models.notification import NotificationKind, NotificationLevel

        session_handler = MagicMock()
        session_handler.get_session.return_value = self._session(
            InstallSessionState.FAILED, error="Installer timed out"
        )
        monkeypatch.setattr(runner, "db_install_session_handler", session_handler)
        monkeypatch.setattr(
            runner,
            "db_rom_handler",
            MagicMock(get_rom_visibility_label=lambda _id: self._rom()),
        )
        notify = AsyncMock()
        monkeypatch.setattr("handler.notification_handler.notify", notify)

        runner._notify_install_end(1)

        args, _ = notify.await_args
        assert args[1] == NotificationKind.INSTALL_FAILED
        assert args[2] == NotificationLevel.ERROR
        assert args[3]["error"] == "Installer timed out"

    def test_non_terminal_state_does_not_notify(self, monkeypatch):
        from models.install_session import InstallSessionState

        session_handler = MagicMock()
        session_handler.get_session.return_value = self._session(
            InstallSessionState.INSTALLING
        )
        monkeypatch.setattr(runner, "db_install_session_handler", session_handler)
        notify = AsyncMock()
        monkeypatch.setattr("handler.notification_handler.notify", notify)

        runner._notify_install_end(1)

        notify.assert_not_awaited()

    def test_a_notify_failure_does_not_raise(self, monkeypatch):
        from models.install_session import InstallSessionState

        session_handler = MagicMock()
        session_handler.get_session.return_value = self._session(
            InstallSessionState.DONE
        )
        monkeypatch.setattr(runner, "db_install_session_handler", session_handler)
        monkeypatch.setattr(
            runner,
            "db_rom_handler",
            MagicMock(get_rom_visibility_label=lambda _id: None),
        )
        monkeypatch.setattr(
            "handler.notification_handler.notify",
            AsyncMock(side_effect=RuntimeError("redis is down")),
        )

        runner._notify_install_end(1)  # must not raise

    def test_run_install_notifies_after_an_unhandled_exception(self, monkeypatch):
        """The `finally` still fires even when `_run_install` itself blows up,
        so a bug in the runner doesn't also leave the owner never notified."""
        monkeypatch.setattr(
            runner, "_run_install", MagicMock(side_effect=RuntimeError("boom"))
        )
        notify_end = MagicMock()
        monkeypatch.setattr(runner, "_notify_install_end", notify_end)

        with pytest.raises(RuntimeError):
            runner.run_install(1)

        notify_end.assert_called_once_with(1)
