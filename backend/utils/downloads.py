"""Helpers for logging served downloads.

Recording is best-effort by design: a stats write must never be the reason a
user's download fails, so every entry point here swallows its own errors.
"""

from __future__ import annotations

from fastapi import Request

from handler.auth.constants import AuthMethod
from handler.database import db_download_handler
from logger.logger import log
from models.download_event import (
    ANONYMOUS_USERNAME,
    CLIENT_IP_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    DownloadKind,
    DownloadSource,
)
from models.rom import Rom, RomFile

_SOURCE_BY_AUTH_METHOD = {
    AuthMethod.SESSION: DownloadSource.WEBUI,
    AuthMethod.BASIC: DownloadSource.BASIC_AUTH,
    AuthMethod.CLIENT_TOKEN: DownloadSource.CLIENT_TOKEN,
    AuthMethod.OAUTH: DownloadSource.OAUTH,
    AuthMethod.KIOSK: DownloadSource.WEBUI,
}


def resolve_download_source(request: Request) -> DownloadSource:
    """Map how the request authenticated onto a download source."""
    auth_method = getattr(request.state, "auth_method", None)
    if auth_method is None:
        return DownloadSource.ANONYMOUS
    return _SOURCE_BY_AUTH_METHOD.get(auth_method, DownloadSource.ANONYMOUS)


def _client_ip(request: Request) -> str | None:
    ip = request.client.host if request.client else None
    return ip[:CLIENT_IP_MAX_LENGTH] if ip else None


def _user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:USER_AGENT_MAX_LENGTH] if ua else None


def record_rom_download(
    request: Request,
    rom: Rom,
    files: list[RomFile],
    kind: DownloadKind = DownloadKind.ROM,
) -> None:
    """Log a served download against `rom`."""
    try:
        user = request.user if request.user.is_authenticated else None
        # The kiosk-mode user is synthetic (id -1) and has no users row, so it
        # gets logged by name only, a real FK would fail the insert.
        user_id = user.id if user and user.id > 0 else None
        db_download_handler.record_download(
            rom=rom,
            user_id=user_id,
            username=user.username if user else ANONYMOUS_USERNAME,
            source=resolve_download_source(request),
            kind=kind,
            file_count=len(files),
            size_bytes=sum(f.file_size_bytes or 0 for f in files),
            client_ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except Exception as exc:  # noqa: BLE001 - stats must never break a download
        log.error(f"Failed to record download for rom {rom.id}: {exc}")
