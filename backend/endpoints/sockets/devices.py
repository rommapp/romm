"""The ``/devices`` socket namespace, open only to device-bound client tokens."""

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Final, NamedTuple

from socketio import exceptions as socketio_exceptions

from config import DEVICE_INSTALL_ENABLED, SESSION_MAX_AGE_SECONDS
from endpoints.responses.device.install import InstallRequestSchema
from handler.auth.constants import CLIENT_TOKEN_PREFIX, Scope
from handler.auth.hybrid_auth import resolve_client_token
from handler.database import db_client_token_handler, db_device_handler
from handler.redis_handler import async_cache
from handler.socket_handler import (
    DEVICES_NAMESPACE,
    client_token_sockets_key,
    socket_handler,
)
from logger.logger import log
from utils.background_tasks import fire_and_forget
from utils.datetime import to_utc

CLIENT_TOKEN_ID_KEY: Final = "client_token_id"
DEVICE_ID_KEY: Final = "device_id"
# Clears entries a crashed worker left behind.
SOCKET_TRACKING_TTL_SECONDS: Final = SESSION_MAX_AGE_SECONDS
# A device is online while one of its sockets, or its last claim, refreshed its
# presence within the TTL.
PRESENCE_TTL_SECONDS: Final = 90
PRESENCE_REFRESH_SECONDS: Final = 30


def device_room(device_id: str) -> str:
    return f"device:{device_id}"


def _presence_key(device_id: str) -> str:
    return f"device_presence:{device_id}"


def _claim_presence_key(device_id: str) -> str:
    return f"device_claim_presence:{device_id}"


def _raw_client_token(environ: dict[str, Any], auth: Any) -> str | None:
    """The token from the handshake's auth payload, else its bearer header."""
    token = auth.get("token") if isinstance(auth, dict) else None
    if isinstance(token, str):
        return token

    scheme, _, credentials = str(environ.get("HTTP_AUTHORIZATION", "")).partition(" ")
    if scheme.lower() == "bearer" and credentials:
        return credentials.strip()
    return None


class BoundToken(NamedTuple):
    token_id: int
    device_id: str
    expires_at: datetime | None


def _bound_token(raw_token: str) -> BoundToken | None:
    """A live, device-bound token holding devices.read."""
    identity = resolve_client_token(raw_token)
    if (
        identity is None
        or not identity.token.device_id
        or Scope.DEVICES_READ not in identity.scopes
    ):
        return None
    expires_at = identity.token.expires_at
    return BoundToken(
        identity.token.id,
        identity.token.device_id,
        to_utc(expires_at) if expires_at else None,
    )


async def _keep_tracked(sid: str, bound: BoundToken) -> None:
    """Refresh the socket's tracking while connected, closing it once its token expires."""
    server = socket_handler.socket_server
    token_id, device_id, expires_at = bound
    while True:
        await server.sleep(PRESENCE_REFRESH_SECONDS)
        if not server.manager.is_connected(sid, DEVICES_NAMESPACE):
            return
        if expires_at and expires_at <= datetime.now(timezone.utc):
            await server.disconnect(sid, namespace=DEVICES_NAMESPACE)
            return
        try:
            await socket_handler.track(
                _presence_key(device_id), sid, PRESENCE_TTL_SECONDS
            )
            await socket_handler.track(
                client_token_sockets_key(token_id), sid, SOCKET_TRACKING_TTL_SECONDS
            )
        except Exception:  # noqa: BLE001
            log.warning(
                f"Failed to refresh the tracking of device {device_id}", exc_info=True
            )


@socket_handler.on("connect", namespace=DEVICES_NAMESPACE)
async def connect(sid: str, environ: dict[str, Any], auth: Any = None) -> None:
    """Admit a live client token bound to a device, whose owner and token hold devices.read."""
    if not DEVICE_INSTALL_ENABLED:
        raise socketio_exceptions.ConnectionRefusedError("disabled")

    raw_token = _raw_client_token(environ, auth)
    if not raw_token or not raw_token.startswith(CLIENT_TOKEN_PREFIX):
        raise socketio_exceptions.ConnectionRefusedError("unauthorized")

    bound = _bound_token(raw_token)
    if bound is None:
        raise socketio_exceptions.ConnectionRefusedError("unauthorized")

    token_id, device_id, _ = bound
    tracking_key = client_token_sockets_key(token_id)
    await socket_handler.track(tracking_key, sid, SOCKET_TRACKING_TTL_SECONDS)
    # A revocation that ran before the socket was tracked found nothing to close.
    if _bound_token(raw_token) != bound:
        await socket_handler.untrack(tracking_key, sid)
        raise socketio_exceptions.ConnectionRefusedError("unauthorized")

    db_client_token_handler.update_last_used(token_id)
    db_device_handler.update_last_seen_debounced(device_id)
    await socket_handler.track(_presence_key(device_id), sid, PRESENCE_TTL_SECONDS)
    async with socket_handler.socket_server.session(
        sid, namespace=DEVICES_NAMESPACE
    ) as session:
        session[CLIENT_TOKEN_ID_KEY] = token_id
        session[DEVICE_ID_KEY] = device_id
    await socket_handler.socket_server.enter_room(
        sid, device_room(device_id), namespace=DEVICES_NAMESPACE
    )
    fire_and_forget(_keep_tracked(sid, bound))


@socket_handler.on("disconnect", namespace=DEVICES_NAMESPACE)
async def disconnect(sid: str) -> None:
    """Forget the socket for revocation and presence."""
    session = await socket_handler.get_session(sid, namespace=DEVICES_NAMESPACE)
    token_id = session.get(CLIENT_TOKEN_ID_KEY)
    device_id = session.get(DEVICE_ID_KEY)
    if token_id is not None:
        await socket_handler.untrack(client_token_sockets_key(token_id), sid)
    if device_id is not None:
        await socket_handler.untrack(_presence_key(device_id), sid)


async def mark_claimed(device_id: str) -> None:
    """Count a device that polls claim instead of holding a socket as online for a while."""
    try:
        await async_cache.set(
            _claim_presence_key(device_id), "1", ex=PRESENCE_TTL_SECONDS
        )
    except Exception:  # noqa: BLE001
        log.warning(f"Failed to record the claim of device {device_id}", exc_info=True)


async def online_device_ids(device_ids: Sequence[str]) -> list[str]:
    """The devices among ``device_ids`` with a socket or a claim that refreshed its presence lately."""
    if not device_ids:
        return []
    async with async_cache.pipeline(transaction=False) as pipe:
        for device_id in device_ids:
            pipe.exists(_presence_key(device_id), _claim_presence_key(device_id))
        counts = await pipe.execute()
    return [
        device_id for device_id, count in zip(device_ids, counts, strict=True) if count
    ]


async def _emit_to_device(event: str, request: InstallRequestSchema) -> None:
    try:
        await socket_handler.write_manager().emit(
            event,
            {"id": request.id, "rom_id": request.rom_id},
            namespace=DEVICES_NAMESPACE,
            room=device_room(request.device_id),
        )
    except Exception:  # noqa: BLE001
        log.warning(
            f"Failed to push {event} to device {request.device_id}", exc_info=True
        )


async def emit_install_queued(request: InstallRequestSchema) -> None:
    """Tell the device a request waits in its queue, logging a failure."""
    await _emit_to_device("install:queued", request)


async def emit_install_cancelled(request: InstallRequestSchema) -> None:
    """Tell the device to drop a request it may already be downloading, logging a failure."""
    await _emit_to_device("install:cancelled", request)


async def emit_install_updated(request: InstallRequestSchema) -> None:
    """Tell the owner's open tabs a request changed."""
    await socket_handler.emit_to_user(
        request.user_id, "install:updated", request.model_dump(mode="json")
    )
