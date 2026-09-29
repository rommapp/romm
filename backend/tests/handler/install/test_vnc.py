import socket

import handler.install.vnc as vnc


class TestWaitForTcpPort:
    def test_returns_true_when_something_is_already_listening(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        try:
            port = server.getsockname()[1]
            assert vnc._wait_for_tcp_port("127.0.0.1", port, timeout=1) is True
        finally:
            server.close()

    def test_returns_false_when_nothing_ever_listens(self):
        # An unused ephemeral port, freed right before the check - nothing
        # should be listening on it.
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()

        assert vnc._wait_for_tcp_port("127.0.0.1", port, timeout=0.1) is False


class TestBuildPublicUrl:
    def test_proxied_mode_points_at_the_backend_and_carries_a_path_override(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            vnc, "INSTALL_VNC_PUBLIC_BASE_URL", "http://localhost:13000"
        )

        url = vnc._build_public_url(6900, "s3cr3t")

        assert url == (
            "http://localhost:13000/api/roms/install/vnc/6900/vnc.html"
            "?autoconnect=true&password=s3cr3t"
            "&path=api/roms/install/vnc/6900/websockify"
            "&resize=scale"
        )

    def test_proxied_mode_strips_a_trailing_slash_from_the_base_url(self, monkeypatch):
        monkeypatch.setattr(
            vnc, "INSTALL_VNC_PUBLIC_BASE_URL", "http://localhost:13000/"
        )

        url = vnc._build_public_url(6900, "s3cr3t")

        assert url.startswith("http://localhost:13000/api/")

    def test_direct_mode_has_no_path_override(self, monkeypatch):
        monkeypatch.setattr(vnc, "INSTALL_VNC_PUBLIC_BASE_URL", "")

        url = vnc._build_public_url(6900, "s3cr3t")

        assert url == (
            "http://127.0.0.1:6900/vnc.html?autoconnect=true&password=s3cr3t"
            "&resize=scale"
        )
        assert "&path=" not in url


class TestClearStaleX11Artifacts:
    def test_removes_an_existing_lock_file_and_socket(self, tmp_path, monkeypatch):
        socket_dir = tmp_path / "X11-unix"
        socket_dir.mkdir()
        monkeypatch.setattr(vnc, "X11_SOCKET_DIR", socket_dir)
        monkeypatch.setattr(vnc, "X11_LOCK_DIR", tmp_path)
        (tmp_path / ".X100-lock").touch()
        (socket_dir / "X100").touch()

        vnc._clear_stale_x11_artifacts(":100")

        assert not (tmp_path / ".X100-lock").exists()
        assert not (socket_dir / "X100").exists()

    def test_is_a_noop_when_nothing_is_there(self, tmp_path, monkeypatch):
        socket_dir = tmp_path / "X11-unix"
        socket_dir.mkdir()
        monkeypatch.setattr(vnc, "X11_SOCKET_DIR", socket_dir)
        monkeypatch.setattr(vnc, "X11_LOCK_DIR", tmp_path)

        vnc._clear_stale_x11_artifacts(":100")  # must not raise


class TestWaitForX11Socket:
    def test_returns_true_immediately_when_socket_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vnc, "X11_SOCKET_DIR", tmp_path)
        (tmp_path / "X99").touch()

        assert vnc._wait_for_x11_socket(":99", timeout=1) is True

    def test_returns_true_once_socket_appears(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vnc, "X11_SOCKET_DIR", tmp_path)

        calls = {"n": 0}
        real_sleep = vnc.time.sleep

        def fake_sleep(seconds):
            calls["n"] += 1
            if calls["n"] == 2:
                (tmp_path / "X50").touch()
            real_sleep(0)  # yield without actually waiting in the test

        monkeypatch.setattr(vnc.time, "sleep", fake_sleep)

        assert vnc._wait_for_x11_socket(":50", timeout=5) is True

    def test_returns_false_when_socket_never_appears(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vnc, "X11_SOCKET_DIR", tmp_path)
        monkeypatch.setattr(vnc.time, "sleep", lambda seconds: None)

        assert vnc._wait_for_x11_socket(":1", timeout=0) is False

    def test_strips_leading_colon_from_display(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vnc, "X11_SOCKET_DIR", tmp_path)
        (tmp_path / "X7").touch()

        assert vnc._wait_for_x11_socket(":7", timeout=1) is True
