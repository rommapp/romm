import json
import socket
from typing import Any

from config import SMB_CONTROLLER_SOCKET, SMB_CONTROLLER_TIMEOUT


class SmbControllerError(Exception):
    pass


class SmbController:
    def request(self, action: str, **payload: Any) -> dict[str, Any]:
        request = json.dumps({"action": action, **payload}, separators=(",", ":"))
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(SMB_CONTROLLER_TIMEOUT)
                client.connect(SMB_CONTROLLER_SOCKET)
                client.sendall(request.encode() + b"\n")
                response = bytearray()
                while not response.endswith(b"\n"):
                    chunk = client.recv(65536)
                    if not chunk:
                        break
                    response.extend(chunk)
                    if len(response) > 1024 * 1024:
                        raise SmbControllerError("SMB controller response is too large")
        except (OSError, TimeoutError) as exc:
            raise SmbControllerError("SMB controller is unavailable") from exc

        try:
            result = json.loads(response)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SmbControllerError("SMB controller returned an invalid response") from exc

        if not result.get("ok"):
            raise SmbControllerError(result.get("error", "SMB controller request failed"))
        return result

    def status(self) -> dict[str, Any]:
        return self.request("status")

    def start(self) -> None:
        self.request("start")

    def restart(self) -> None:
        self.request("restart")

    def logs(self, limit: int) -> list[str]:
        result = self.request("logs", limit=limit)
        lines = result.get("lines")
        if not isinstance(lines, list) or not all(
            isinstance(line, str) for line in lines
        ):
            raise SmbControllerError("SMB controller returned invalid logs")
        return lines

    def create_user(self, username: str, password: str) -> None:
        self.request("create_user", username=username, password=password)

    def rotate_user(self, username: str, password: str) -> None:
        self.request("rotate_user", username=username, password=password)

    def delete_user(self, username: str) -> None:
        self.request("delete_user", username=username)

    def sync_config(self, users: list[dict[str, Any]]) -> None:
        self.request("sync_config", users=users)


smb_controller = SmbController()
