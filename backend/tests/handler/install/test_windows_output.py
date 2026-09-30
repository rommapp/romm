from handler.install.windows_output import (
    collect_extra_work_dir_files,
    collect_windows_install_files,
    resolve_install_root,
    snapshot_windows_content_files,
)


class TestCollectWindowsInstallFiles:
    def test_finds_files_under_program_files(self, tmp_path):
        game_dir = tmp_path / "drive_c" / "Program Files" / "MyGame"
        game_dir.mkdir(parents=True)
        (game_dir / "game.exe").write_bytes(b"x")
        (game_dir / "data.pak").write_bytes(b"yy")

        found = collect_windows_install_files(tmp_path)
        names = {p.name for p in found}
        assert names == {"game.exe", "data.pak"}

    def test_finds_files_under_program_files_x86(self, tmp_path):
        game_dir = tmp_path / "drive_c" / "Program Files (x86)" / "MyGame"
        game_dir.mkdir(parents=True)
        (game_dir / "game.exe").write_bytes(b"x")

        found = collect_windows_install_files(tmp_path)
        assert len(found) == 1

    def test_finds_files_under_a_custom_install_path(self, tmp_path):
        # Installers that default outside Program Files (e.g. a custom
        # C:\Games\... target) must still be discovered.
        game_dir = tmp_path / "drive_c" / "GOG Games" / "MyGame"
        game_dir.mkdir(parents=True)
        (game_dir / "game.exe").write_bytes(b"x")

        found = collect_windows_install_files(tmp_path)
        assert {p.name for p in found} == {"game.exe"}

    def test_ignores_blacklisted_system_directories(self, tmp_path):
        (tmp_path / "drive_c" / "windows" / "system32").mkdir(parents=True)
        (tmp_path / "drive_c" / "windows" / "system32" / "ntdll.dll").write_bytes(b"x")
        (tmp_path / "drive_c" / "programdata" / "stuff").mkdir(parents=True)
        (tmp_path / "drive_c" / "programdata" / "stuff" / "note.txt").write_bytes(b"x")

        assert collect_windows_install_files(tmp_path) == []

    def test_ignores_proton_shortcuts(self, tmp_path):
        shortcuts = tmp_path / "drive_c" / "proton_shortcuts"
        shortcuts.mkdir(parents=True)
        (shortcuts / "Game.lnk").write_bytes(b"x")

        assert collect_windows_install_files(tmp_path) == []

    def test_ignores_appdata_local_temp_for_any_user(self, tmp_path):
        temp_dir = (
            tmp_path / "drive_c" / "users" / "steamuser" / "AppData" / "Local" / "Temp"
        )
        temp_dir.mkdir(parents=True)
        (temp_dir / "installer_extract.tmp").write_bytes(b"x")

        assert collect_windows_install_files(tmp_path) == []

    def test_does_not_ignore_appdata_roaming(self, tmp_path):
        # Only Local/Temp is blacklisted - Roaming commonly holds real
        # config/save data an installer legitimately writes.
        roaming = (
            tmp_path
            / "drive_c"
            / "users"
            / "steamuser"
            / "AppData"
            / "Roaming"
            / "MyGame"
        )
        roaming.mkdir(parents=True)
        (roaming / "config.ini").write_bytes(b"x")

        found = collect_windows_install_files(tmp_path)
        assert {p.name for p in found} == {"config.ini"}

    def test_missing_prefix_returns_empty(self, tmp_path):
        assert collect_windows_install_files(tmp_path / "does-not-exist") == []

    def test_excludes_files_present_in_the_baseline(self, tmp_path):
        # Wine's own bootstrap stubs (wmplayer.exe, ...) - present before the
        # installer ever runs, must never count as "what it wrote".
        stub = tmp_path / "drive_c" / "Program Files" / "Windows Media Player"
        stub.mkdir(parents=True)
        (stub / "wmplayer.exe").write_bytes(b"stub")
        baseline = snapshot_windows_content_files(tmp_path)

        game_dir = tmp_path / "drive_c" / "Program Files" / "MyGame"
        game_dir.mkdir(parents=True)
        (game_dir / "game.exe").write_bytes(b"real game")

        found = collect_windows_install_files(tmp_path, baseline)
        assert {p.name for p in found} == {"game.exe"}

    def test_excludes_synthesized_user_profile_files_present_in_the_baseline(
        self, tmp_path
    ):
        # `users/` isn't blacklisted (installers legitimately write shortcuts/
        # config there), so Wine's own synthesized profile tree is filtered
        # via the same before/after baseline diff as Program Files' stubs.
        profile = tmp_path / "drive_c" / "users" / "steamuser" / "Desktop"
        profile.mkdir(parents=True)
        (profile / "desktop.ini").write_bytes(b"wine stub")
        baseline = snapshot_windows_content_files(tmp_path)

        save_dir = tmp_path / "drive_c" / "users" / "steamuser" / "AppData" / "MyGame"
        save_dir.mkdir(parents=True)
        (save_dir / "save.dat").write_bytes(b"actual save data")

        found = collect_windows_install_files(tmp_path, baseline)
        assert {p.name for p in found} == {"save.dat"}

    def test_baseline_of_zero_files_excludes_nothing(self, tmp_path):
        game_dir = tmp_path / "drive_c" / "Program Files" / "MyGame"
        game_dir.mkdir(parents=True)
        (game_dir / "game.exe").write_bytes(b"x")

        assert collect_windows_install_files(tmp_path, frozenset()) == (
            collect_windows_install_files(tmp_path)
        )


class TestSnapshotWindowsContentFiles:
    def test_captures_files_across_drive_c(self, tmp_path):
        (tmp_path / "drive_c" / "Program Files" / "A").mkdir(parents=True)
        (tmp_path / "drive_c" / "Program Files" / "A" / "a.exe").write_bytes(b"x")
        (tmp_path / "drive_c" / "Program Files (x86)" / "B").mkdir(parents=True)
        (tmp_path / "drive_c" / "Program Files (x86)" / "B" / "b.exe").write_bytes(b"y")
        (tmp_path / "drive_c" / "users" / "steamuser").mkdir(parents=True)
        (tmp_path / "drive_c" / "users" / "steamuser" / "c.txt").write_bytes(b"z")

        snapshot = snapshot_windows_content_files(tmp_path)
        assert {p.name for p in snapshot} == {"a.exe", "b.exe", "c.txt"}

    def test_does_not_capture_blacklisted_system_directories(self, tmp_path):
        (tmp_path / "drive_c" / "windows" / "system32").mkdir(parents=True)
        (tmp_path / "drive_c" / "windows" / "system32" / "ntdll.dll").write_bytes(b"x")

        assert snapshot_windows_content_files(tmp_path) == frozenset()

    def test_empty_prefix_snapshots_to_empty(self, tmp_path):
        assert snapshot_windows_content_files(tmp_path) == frozenset()


class TestResolveInstallRoot:
    def test_roots_inside_a_single_known_vendor_folder(self, tmp_path):
        drive_c = tmp_path / "drive_c"
        game_dir = drive_c / "GOG Games" / "Freedom Planet"
        game_dir.mkdir(parents=True)
        files = [game_dir / "game.exe", game_dir / "data.pak"]

        assert resolve_install_root(drive_c, files) == drive_c / "GOG Games"

    def test_roots_inside_program_files_when_thats_the_only_folder(self, tmp_path):
        drive_c = tmp_path / "drive_c"
        game_dir = drive_c / "Program Files" / "MyGame"
        game_dir.mkdir(parents=True)
        files = [game_dir / "game.exe"]

        assert resolve_install_root(drive_c, files) == drive_c / "Program Files"

    def test_falls_back_to_drive_c_when_files_span_multiple_top_level_folders(
        self, tmp_path
    ):
        drive_c = tmp_path / "drive_c"
        files = [
            drive_c / "GOG Games" / "Freedom Planet" / "game.exe",
            drive_c / "users" / "steamuser" / "Desktop" / "shortcut.lnk",
        ]

        assert resolve_install_root(drive_c, files) == drive_c

    def test_falls_back_to_drive_c_when_the_sole_folder_is_not_a_known_vendor(
        self, tmp_path
    ):
        drive_c = tmp_path / "drive_c"
        files = [drive_c / "SomeRandomInstallerDir" / "game.exe"]

        assert resolve_install_root(drive_c, files) == drive_c

    def test_empty_files_falls_back_to_drive_c(self, tmp_path):
        drive_c = tmp_path / "drive_c"
        assert resolve_install_root(drive_c, []) == drive_c


class TestCollectExtraWorkDirFiles:
    """Regression coverage for a real gap: z:\\ can't actually be removed
    (Proton recreates it on every real launch regardless of what it's told
    to run - see runner._configure_drive_letters), so an installer that
    resolves its own location through it and writes "next to itself" -
    into work_dir, the one thing z:\\ exposes that's actually recoverable
    (a real bind mount, unlike the sandboxed installer's own /tmp: a fresh
    tmpfs private to its mount namespace, gone the moment its process
    exits) - was possible in principle and went completely untracked.
    """

    def test_finds_a_file_written_directly_into_work_dir(self, tmp_path):
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        (work_dir / "stray.dat").write_bytes(b"x")

        found = collect_extra_work_dir_files(work_dir)

        assert {p.name for p in found} == {"stray.dat"}

    def test_finds_files_under_a_stray_subfolder(self, tmp_path):
        work_dir = tmp_path / "work"
        game_dir = work_dir / "SomeGame"
        game_dir.mkdir(parents=True)
        (game_dir / "data.bin").write_bytes(b"x")

        found = collect_extra_work_dir_files(work_dir)

        assert {p.name for p in found} == {"data.bin"}

    def test_ignores_the_wine_prefix_and_its_own_drive_c_content(self, tmp_path):
        work_dir = tmp_path / "work"
        drive_c = work_dir / "prefix" / "pfx" / "drive_c"
        drive_c.mkdir(parents=True)
        (drive_c / "Program Files" / "MyGame").mkdir(parents=True)
        (drive_c / "Program Files" / "MyGame" / "game.exe").write_bytes(b"x")
        (work_dir / "prefix" / "pfx" / "system.reg").write_bytes(b"wine state")

        assert collect_extra_work_dir_files(work_dir) == []

    def test_ignores_the_proton_stub_client_dir(self, tmp_path):
        work_dir = tmp_path / "work"
        (work_dir / "steam-client" / "steamclient.dll").parent.mkdir(parents=True)
        (work_dir / "steam-client" / "steamclient.dll").write_bytes(b"x")

        assert collect_extra_work_dir_files(work_dir) == []

    def test_ignores_this_sessions_own_manifest_files(self, tmp_path):
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        (work_dir / ".romm-install-manifest.json").write_bytes(b"{}")
        (work_dir / ".romm-install-manifest.live.json").write_bytes(b"{}")

        assert collect_extra_work_dir_files(work_dir) == []

    def test_missing_work_dir_returns_empty(self, tmp_path):
        assert collect_extra_work_dir_files(tmp_path / "does-not-exist") == []
