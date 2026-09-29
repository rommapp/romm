from handler.install.sandbox import SandboxSpec, build_bwrap_command


def _spec(**overrides) -> SandboxSpec:
    base = dict(
        installer_path="/library/win/game/setup.exe",
        work_dir="/cache/installs/1",
        proton_prefix="/cache/installs/1/prefix",
        display=":99",
    )
    base.update(overrides)
    return SandboxSpec(**base)


class TestBuildBwrapCommand:
    def test_starts_with_bwrap_and_ends_with_inner_command(self):
        argv = build_bwrap_command(_spec(), ["wine", "/library/win/game/setup.exe"])
        assert argv[0] == "bwrap"
        assert argv[-2:] == ["wine", "/library/win/game/setup.exe"]

    def test_network_is_unshared(self):
        argv = build_bwrap_command(_spec(), ["true"])
        assert "--unshare-net" in argv

    def test_other_namespaces_are_unshared_but_not_ipc(self):
        # IPC must stay shared with the container's own namespace: Wine's
        # X11 driver blits its windows via MIT-SHM (XShmPutImage), which
        # needs a System V shared memory segment the X server - running
        # outside the sandbox - can actually attach to. Unsharing IPC here
        # breaks that silently (the window maps and sizes fine, its content
        # just never paints).
        argv = build_bwrap_command(_spec(), ["true"])
        assert "--unshare-all" not in argv
        assert "--unshare-ipc" not in argv
        for flag in (
            "--unshare-user",
            "--unshare-pid",
            "--unshare-uts",
            "--unshare-cgroup",
        ):
            assert flag in argv

    def test_installer_bound_read_only(self):
        spec = _spec()
        argv = build_bwrap_command(spec, ["true"])
        # The installer path must appear as a --ro-bind source, never --bind.
        ro_pairs = [
            (argv[i + 1], argv[i + 2])
            for i, a in enumerate(argv)
            if a == "--ro-bind" and i + 2 < len(argv)
        ]
        assert (spec.installer_path, spec.installer_path) in ro_pairs

    def test_work_dir_and_prefix_are_writable(self):
        spec = _spec()
        argv = build_bwrap_command(spec, ["true"])
        bind_pairs = [
            (argv[i + 1], argv[i + 2])
            for i, a in enumerate(argv)
            if a == "--bind" and i + 2 < len(argv)
        ]
        assert (spec.work_dir, spec.work_dir) in bind_pairs
        assert (spec.proton_prefix, spec.proton_prefix) in bind_pairs

    def test_library_is_never_bound(self):
        spec = _spec()
        argv = build_bwrap_command(spec, ["true"])
        # Only the installer file itself is exposed from the library, never the
        # ROM directory or any broader library path.
        assert "/library" not in argv
        assert "/library/win/game" not in argv

    def test_display_and_wineprefix_env_are_set(self):
        spec = _spec()
        argv = build_bwrap_command(spec, ["true"])
        joined = " ".join(argv)
        assert "--setenv DISPLAY :99" in joined
        assert f"--setenv WINEPREFIX {spec.proton_prefix}" in joined

    def test_x11_socket_dir_is_rebound_read_only(self):
        # Xvfb's socket lives under the host's real /tmp, which --tmpfs /tmp
        # hides; without rebinding it, DISPLAY is unreachable inside the
        # sandbox and the installer can never connect.
        spec = _spec()
        argv = build_bwrap_command(spec, ["true"])
        ro_pairs = [
            (argv[i + 1], argv[i + 2])
            for i, a in enumerate(argv)
            if a == "--ro-bind" and i + 2 < len(argv)
        ]
        assert ("/tmp/.X11-unix", "/tmp/.X11-unix") in ro_pairs
        # Must come after --tmpfs /tmp so it lands inside the fresh mount.
        tmpfs_idx = argv.index("--tmpfs")
        x11_idx = argv.index("/tmp/.X11-unix")
        assert x11_idx > tmpfs_idx

    def test_dri_device_is_rebound(self):
        # --dev /dev gives the sandbox a fresh, minimal /dev with no GPU
        # nodes at all - without re-binding the real render node, Wine/Proton
        # falls back to pure CPU rendering for every GL/GLX call.
        spec = _spec()
        argv = build_bwrap_command(spec, ["true"])
        dev_bind_try_pairs = [
            (argv[i + 1], argv[i + 2])
            for i, a in enumerate(argv)
            if a == "--dev-bind-try" and i + 2 < len(argv)
        ]
        assert ("/dev/dri", "/dev/dri") in dev_bind_try_pairs
        # Must come after --dev /dev so it lands inside the fresh /dev.
        dev_idx = argv.index("--dev")
        dri_idx = argv.index("/dev/dri")
        assert dri_idx > dev_idx

    def test_etc_alternatives_is_bound_read_only(self):
        # /usr/bin/wine is a Debian update-alternatives symlink pointing
        # outside /usr; without this, execing "wine" fails inside the
        # sandbox even though /usr/bin/wine itself is bound.
        spec = _spec()
        argv = build_bwrap_command(spec, ["true"])
        ro_try_pairs = [
            (argv[i + 1], argv[i + 2])
            for i, a in enumerate(argv)
            if a == "--ro-bind-try" and i + 2 < len(argv)
        ]
        assert ("/etc/alternatives", "/etc/alternatives") in ro_try_pairs

    def test_extra_ro_binds_are_included(self):
        spec = _spec(ro_binds=("/opt/proton",))
        argv = build_bwrap_command(spec, ["true"])
        ro_pairs = [
            (argv[i + 1], argv[i + 2])
            for i, a in enumerate(argv)
            if a == "--ro-bind" and i + 2 < len(argv)
        ]
        assert ("/opt/proton", "/opt/proton") in ro_pairs

    def test_extra_env_is_set_on_top_of_display_and_wineprefix(self):
        spec = _spec(
            extra_env=(
                ("STEAM_COMPAT_DATA_PATH", "/cache/installs/1/prefix"),
                ("STEAM_COMPAT_CLIENT_INSTALL_PATH", "/cache/installs/1/steam-client"),
            )
        )
        argv = build_bwrap_command(spec, ["true"])
        joined = " ".join(argv)
        assert "--setenv DISPLAY :99" in joined
        assert "--setenv WINEPREFIX /cache/installs/1/prefix" in joined
        assert "--setenv STEAM_COMPAT_DATA_PATH /cache/installs/1/prefix" in joined
        assert (
            "--setenv STEAM_COMPAT_CLIENT_INSTALL_PATH /cache/installs/1/steam-client"
            in joined
        )

    def test_no_extra_env_by_default(self):
        argv = build_bwrap_command(_spec(), ["true"])
        assert "STEAM_COMPAT_DATA_PATH" not in " ".join(argv)
