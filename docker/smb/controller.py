#!/usr/bin/env python3

import json
import os
import pwd
import re
import signal
import socket
import socketserver
import struct
import subprocess
import tempfile
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CONFIG_TEMPLATE = Path("/etc/samba/smb.conf.template")
CONFIG_PATH = Path("/run/samba/smb.conf")
CONTROL_SOCKET = Path("/run/romm-smb/control.sock")
LIBRARY_PATH = Path("/library")
MANAGED_USERS_PATH = Path("/var/lib/samba/romm-managed-users.json")
MAX_REQUEST_BYTES = 1024 * 1024
MAX_LOG_LINES = 500
MAX_LOG_BYTES = 256 * 1024
MAX_LOG_FILES = 20
USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{2,31}$")
SHARE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
ALLOWED_PEER_UIDS = {0, 1000}


class ControllerError(Exception):
    pass


def run_command(
    command: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        input=input_text,
        text=True,
        check=check,
        capture_output=True,
    )


class SmbController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._smbd: subprocess.Popen[str] | None = None
        self._started_at: str | None = None
        self._events: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self._configured_shares: set[str] = set()
        self._prepare_directories()
        self._managed_unix_users = self._load_managed_unix_users()
        self._write_base_config()
        self._restore_unix_users()
        self._record_event("SMB controller initialized")

    def start_samba(self) -> None:
        if self.samba_running():
            return
        self._smbd = subprocess.Popen(
            [
                "smbd",
                "--foreground",
                "--no-process-group",
                f"--configfile={CONFIG_PATH}",
            ],
            start_new_session=True,
        )
        self._started_at = datetime.now(UTC).isoformat()
        self._record_event("Samba service started")

    def stop_samba(self) -> None:
        if self._smbd is None:
            return
        if self._smbd.poll() is not None:
            self._started_at = None
            return
        self._smbd.terminate()
        try:
            self._smbd.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._smbd.kill()
            self._smbd.wait(timeout=5)
        self._started_at = None
        self._record_event("Samba service stopped")

    def samba_running(self) -> bool:
        return self._smbd is not None and self._smbd.poll() is None

    def reap_orphaned_children(self) -> None:
        active_smbd_pid = self._smbd.pid if self._smbd is not None else None
        for status_path in Path("/proc").glob("[0-9]*/status"):
            pid = int(status_path.parent.name)
            if pid == active_smbd_pid:
                continue
            try:
                status_lines = status_path.read_text().splitlines()
            except (FileNotFoundError, ProcessLookupError):
                continue
            state = next(
                (
                    line.split(":", 1)[1].strip()
                    for line in status_lines
                    if line.startswith("State:")
                ),
                "",
            )
            parent_pid = next(
                (
                    line.split(":", 1)[1].strip()
                    for line in status_lines
                    if line.startswith("PPid:")
                ),
                "",
            )
            if state.startswith("Z") and parent_pid == str(os.getpid()):
                try:
                    os.waitpid(pid, os.WNOHANG)
                except (ChildProcessError, ProcessLookupError):
                    pass

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        action = request.get("action")
        with self._lock:
            if action == "status":
                version = run_command(["smbd", "--version"]).stdout.strip()
                return {
                    "ok": True,
                    "samba_running": self.samba_running(),
                    "samba_version": version,
                    "started_at": self._started_at,
                    "workgroup": os.environ.get("ROMM_SMB_WORKGROUP", "WORKGROUP"),
                }
            if action == "start":
                self.start_samba()
                self._wait_until_running()
                return {"ok": True}
            if action == "restart":
                self.stop_samba()
                self.start_samba()
                self._wait_until_running()
                return {"ok": True}
            if action == "logs":
                return {"ok": True, "lines": self._logs(request.get("limit"))}
            if action == "create_user":
                self._set_password(
                    self._username(request), self._password(request), create=True
                )
                self._record_event("SMB user created")
                return {"ok": True}
            if action == "rotate_user":
                self._set_password(
                    self._username(request), self._password(request), create=False
                )
                self._record_event("SMB user password regenerated")
                return {"ok": True}
            if action == "delete_user":
                self._delete_user(self._username(request))
                self._record_event("SMB user deleted")
                return {"ok": True}
            if action == "sync_config":
                self._sync_config(request.get("users"))
                self._record_event("SMB configuration synchronized")
                return {"ok": True}
        raise ControllerError("Unsupported controller action")

    def _wait_until_running(self) -> None:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not self.samba_running():
                raise ControllerError("Samba failed to start")
            result = run_command(
                [
                    "smbcontrol",
                    "--configfile",
                    str(CONFIG_PATH),
                    "smbd",
                    "ping",
                ],
                check=False,
            )
            if result.returncode == 0:
                return
            time.sleep(0.2)
        raise ControllerError("Samba did not become ready")

    def _record_event(self, message: str) -> None:
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        self._events.append(f"{timestamp} controller: {message}")

    def _logs(self, requested_limit: Any) -> list[str]:
        if not isinstance(requested_limit, int) or isinstance(requested_limit, bool):
            raise ControllerError("Log limit must be an integer")
        if requested_limit < 1 or requested_limit > MAX_LOG_LINES:
            raise ControllerError(f"Log limit must be between 1 and {MAX_LOG_LINES}")

        lines = list(self._events)
        log_root = Path("/var/log/samba").resolve()
        remaining_bytes = MAX_LOG_BYTES

        def modification_time(path: Path) -> float:
            try:
                return path.stat().st_mtime
            except OSError:
                return 0

        log_paths = sorted(
            log_root.glob("log.*"),
            key=modification_time,
            reverse=True,
        )[:MAX_LOG_FILES]
        for log_path in log_paths:
            if remaining_bytes <= 0:
                break
            resolved_path = log_path.resolve()
            if (
                not resolved_path.is_relative_to(log_root)
                or not resolved_path.is_file()
            ):
                continue
            with resolved_path.open("rb") as log_file:
                log_file.seek(0, os.SEEK_END)
                size = log_file.tell()
                bytes_to_read = min(remaining_bytes, size)
                log_file.seek(max(0, size - bytes_to_read))
                raw_content = log_file.read(bytes_to_read)
                remaining_bytes -= len(raw_content)
                content = raw_content.decode(
                    "utf-8", errors="replace"
                )
            source = resolved_path.name
            lines.extend(
                f"{source}: {line[:2000]}"
                for line in content.splitlines()
                if line.strip()
            )
        return lines[-requested_limit:]

    def _prepare_directories(self) -> None:
        for directory in (
            Path("/run/samba/ncalrpc"),
            Path("/run/romm-smb"),
            Path("/var/cache/samba"),
            Path("/var/lib/samba/private"),
            Path("/var/lib/samba/usershares"),
            Path("/var/log/samba"),
        ):
            directory.mkdir(parents=True, exist_ok=True)
        os.chown("/run/romm-smb", 0, 1000)
        os.chmod("/run/romm-smb", 0o750)

    def _write_base_config(self) -> None:
        workgroup = os.environ.get("ROMM_SMB_WORKGROUP", "WORKGROUP")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,15}", workgroup):
            raise ControllerError("ROMM_SMB_WORKGROUP is invalid")
        config = CONFIG_TEMPLATE.read_text().replace("{{SMB_WORKGROUP}}", workgroup)
        self._replace_config(config)

    def _restore_unix_users(self) -> None:
        result = run_command(
            ["pdbedit", "-s", str(CONFIG_PATH), "-L"], check=False
        )
        if result.returncode not in (0, 1):
            raise ControllerError("Unable to read the Samba user database")
        for line in result.stdout.splitlines():
            username = line.split(":", 1)[0]
            if USERNAME_PATTERN.fullmatch(username):
                if username not in self._managed_unix_users:
                    try:
                        existing_user = pwd.getpwnam(username)
                    except KeyError:
                        existing_user = None
                    if existing_user is not None and not self._is_managed_unix_user(
                        existing_user
                    ):
                        run_command(
                            [
                                "smbpasswd",
                                "-c",
                                str(CONFIG_PATH),
                                "-x",
                                username,
                            ],
                            check=False,
                        )
                        self._record_event(
                            "Removed an SMB credential that conflicted with a system account"
                        )
                        continue
                    self._managed_unix_users.add(username)
                    self._save_managed_unix_users()
                self._ensure_unix_user(username)

    def _load_managed_unix_users(self) -> set[str]:
        if not MANAGED_USERS_PATH.exists():
            return set()
        try:
            data = json.loads(MANAGED_USERS_PATH.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ControllerError("Managed SMB user registry is invalid") from exc
        if not isinstance(data, list) or not all(
            isinstance(username, str) and USERNAME_PATTERN.fullmatch(username)
            for username in data
        ):
            raise ControllerError("Managed SMB user registry is invalid")

        managed_users = set(data)
        for username in tuple(managed_users):
            try:
                existing_user = pwd.getpwnam(username)
            except KeyError:
                continue
            if not self._is_managed_unix_user(existing_user):
                managed_users.remove(username)
        if managed_users != set(data):
            self._managed_unix_users = managed_users
            self._save_managed_unix_users()
        return managed_users

    def _save_managed_unix_users(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=MANAGED_USERS_PATH.parent, delete=False
        ) as temporary:
            json.dump(sorted(self._managed_unix_users), temporary)
            temporary.write("\n")
            temporary_path = Path(temporary.name)
        try:
            os.chmod(temporary_path, 0o600)
            temporary_path.replace(MANAGED_USERS_PATH)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _is_managed_unix_user(self, user: pwd.struct_passwd) -> bool:
        romm_group_id = pwd.getpwnam("romm").pw_gid
        return (
            user.pw_name != "romm"
            and user.pw_gid == romm_group_id
            and user.pw_shell in ("/sbin/nologin", "/usr/sbin/nologin")
        )

    def _ensure_unix_user(self, username: str) -> None:
        try:
            existing_user = pwd.getpwnam(username)
        except KeyError:
            existing_user = None

        if existing_user is not None:
            if username in self._managed_unix_users and self._is_managed_unix_user(
                existing_user
            ):
                return
            raise ControllerError("SMB username conflicts with a system account")

        run_command(
            [
                "adduser",
                "-D",
                "-H",
                "-S",
                "-G",
                "romm",
                "-s",
                "/sbin/nologin",
                username,
            ]
        )
        self._managed_unix_users.add(username)
        self._save_managed_unix_users()

    def _set_password(self, username: str, password: str, *, create: bool) -> None:
        self._ensure_unix_user(username)
        command = ["smbpasswd", "-c", str(CONFIG_PATH)]
        if create:
            command.append("-a")
        command.extend(["-s", username])
        result = run_command(
            command,
            input_text=f"{password}\n{password}\n",
            check=False,
        )
        if result.returncode != 0:
            raise ControllerError("Unable to update the SMB credential")

    def _delete_user(self, username: str) -> None:
        run_command(
            ["smbpasswd", "-c", str(CONFIG_PATH), "-x", username], check=False
        )
        if username not in self._managed_unix_users:
            return
        try:
            existing_user = pwd.getpwnam(username)
        except KeyError:
            existing_user = None
        if existing_user is not None and self._is_managed_unix_user(existing_user):
            run_command(["deluser", username], check=False)
        self._managed_unix_users.discard(username)
        self._save_managed_unix_users()

    def _sync_config(self, users: Any) -> None:
        if not isinstance(users, list):
            raise ControllerError("Controller users must be a list")

        shares: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(
            lambda: {"read": set(), "write": set()}
        )
        for user in users:
            if not isinstance(user, dict):
                raise ControllerError("Controller user is invalid")
            username = self._validate_username(user.get("username"))
            permissions = user.get("permissions")
            if not isinstance(permissions, list):
                raise ControllerError("Controller permissions must be a list")
            for permission in permissions:
                if not isinstance(permission, dict):
                    raise ControllerError("Controller permission is invalid")
                share_name = permission.get("share_name")
                if not isinstance(share_name, str) or not SHARE_PATTERN.fullmatch(
                    share_name
                ):
                    raise ControllerError("SMB share name is invalid")
                path = self._validate_library_path(permission.get("path"))
                access = permission.get("access")
                if access not in ("read", "write"):
                    raise ControllerError("SMB access mode is invalid")
                shares[(share_name, path)][access].add(username)

        base = CONFIG_TEMPLATE.read_text().replace(
            "{{SMB_WORKGROUP}}", os.environ.get("ROMM_SMB_WORKGROUP", "WORKGROUP")
        )
        sections = [base.rstrip()]
        for (share_name, path), access_lists in sorted(shares.items()):
            readers = sorted(access_lists["read"])
            writers = sorted(access_lists["write"])
            valid_users = sorted(set(readers + writers))
            lines = [
                f"[{share_name}]",
                f"path = {path}",
                "read only = yes",
                "guest ok = no",
                "browseable = yes",
                f"valid users = {' '.join(valid_users)}",
                "force user = romm",
                "force group = romm",
                "create mask = 0664",
                "directory mask = 0775",
                "follow symlinks = no",
                "wide links = no",
            ]
            if readers:
                lines.append(f"read list = {' '.join(readers)}")
            if writers:
                lines.append(f"write list = {' '.join(writers)}")
            sections.append("\n".join(lines))

        previous_shares = self._configured_shares
        configured_shares = {share_name for share_name, _path in shares}
        self._replace_config("\n\n".join(sections) + "\n")
        if self.samba_running():
            result = run_command(
                [
                    "smbcontrol",
                    "--configfile",
                    str(CONFIG_PATH),
                    "smbd",
                    "reload-config",
                ],
                check=False,
            )
            if result.returncode != 0:
                raise ControllerError("Unable to reload the SMB configuration")
            for share_name in sorted(previous_shares | configured_shares):
                result = run_command(
                    [
                        "smbcontrol",
                        "--configfile",
                        str(CONFIG_PATH),
                        "smbd",
                        "close-share",
                        share_name,
                    ],
                    check=False,
                )
                if result.returncode != 0:
                    raise ControllerError(
                        "Unable to disconnect clients from an updated SMB share"
                    )
        self._configured_shares = configured_shares

    def _replace_config(self, config: str) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=CONFIG_PATH.parent, delete=False
        ) as temporary:
            temporary.write(config)
            temporary_path = Path(temporary.name)
        try:
            result = run_command(
                ["testparm", "-s", str(temporary_path)], check=False
            )
            if result.returncode != 0:
                raise ControllerError("Generated SMB configuration is invalid")
            os.chmod(temporary_path, 0o600)
            temporary_path.replace(CONFIG_PATH)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _username(self, request: dict[str, Any]) -> str:
        return self._validate_username(request.get("username"))

    def _validate_username(self, username: Any) -> str:
        if not isinstance(username, str) or not USERNAME_PATTERN.fullmatch(username):
            raise ControllerError("SMB username is invalid")
        if username == "romm":
            raise ControllerError("SMB username is reserved")
        return username

    def _password(self, request: dict[str, Any]) -> str:
        password = request.get("password")
        if (
            not isinstance(password, str)
            or len(password) < 16
            or len(password) > 128
            or "\n" in password
            or "\r" in password
        ):
            raise ControllerError("SMB password is invalid")
        return password

    def _validate_library_path(self, relative_path: Any) -> str:
        if not isinstance(relative_path, str) or any(
            character in relative_path for character in ("\x00", "\n", "\r")
        ):
            raise ControllerError("SMB library path is invalid")
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ControllerError("SMB library path is invalid")
        root = LIBRARY_PATH.resolve()
        candidate = (root / relative).resolve()
        candidate_path = str(candidate)
        if (
            not candidate.is_relative_to(root)
            or not candidate.is_dir()
            or any(character in candidate_path for character in ("\x00", "\n", "\r"))
        ):
            raise ControllerError("SMB platform directory does not exist")
        return candidate_path


controller = SmbController()


class ControlHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        credentials = self.request.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")
        )
        _, peer_uid, _ = struct.unpack("3i", credentials)
        if peer_uid not in ALLOWED_PEER_UIDS:
            self._respond({"ok": False, "error": "Controller access denied"})
            return

        request_data = self.rfile.readline(MAX_REQUEST_BYTES + 1)
        if len(request_data) > MAX_REQUEST_BYTES:
            self._respond({"ok": False, "error": "Controller request is too large"})
            return
        try:
            request = json.loads(request_data)
            if not isinstance(request, dict):
                raise ControllerError("Controller request is invalid")
            response = controller.handle(request)
        except (ControllerError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            response = {"ok": False, "error": str(exc)}
        # Keep unexpected command/runtime details off the control protocol.
        except Exception:  # noqa: BLE001
            response = {"ok": False, "error": "Internal controller error"}
        self._respond(response)

    def _respond(self, response: dict[str, Any]) -> None:
        self.wfile.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")


class ControlServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True


def main() -> None:
    CONTROL_SOCKET.unlink(missing_ok=True)
    server = ControlServer(str(CONTROL_SOCKET), ControlHandler)
    os.chown(CONTROL_SOCKET, 0, 1000)
    os.chmod(CONTROL_SOCKET, 0o660)

    stop = threading.Event()

    def request_stop(_signum: int, _frame: Any) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    controller.start_samba()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        while not stop.is_set():
            controller.reap_orphaned_children()
            time.sleep(0.5)
    finally:
        server.shutdown()
        server.server_close()
        CONTROL_SOCKET.unlink(missing_ok=True)
        controller.stop_samba()


if __name__ == "__main__":
    main()
