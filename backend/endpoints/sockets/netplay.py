"""Netplay rooms over Socket.IO, gated on the ROM being played.

A guest may bypass that gate with the owner's room password.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from endpoints.netplay import DEFAULT_MAX_PLAYERS
from handler.auth.constants import Scope
from handler.auth.permissions import resolve_permissions
from handler.database import db_rom_handler, db_user_handler
from handler.netplay_handler import NetplayPlayerInfo, NetplayRoom, netplay_handler
from handler.socket_handler import netplay_socket_handler
from logger.logger import log
from utils.auth import get_session_from_environ

if TYPE_CHECKING:
    from models.user import User

# Session keys. The connect-time identity and the room membership share one
# server-side session dict, so every read goes through these names.
AUTH_USER_SESSION_KEY = "netplay_auth_user_id"
ROOM_SESSION_KEY = "session_id"
PLAYER_SESSION_KEY = "player_id"


class RoomDataExtra(TypedDict):
    sessionid: str | None
    userid: str | None
    playerId: str | None
    room_name: NotRequired[str]
    game_id: NotRequired[str]
    domain: NotRequired[str]
    player_name: NotRequired[str]
    room_password: NotRequired[str]


class RoomData(TypedDict):
    extra: RoomDataExtra
    maxPlayers: NotRequired[int]


class WebRTCSignalData(TypedDict, total=False):
    target: str
    candidate: Any
    offer: Any
    answer: Any
    requestRenegotiate: bool


async def _get_session(sid: str) -> dict[str, Any]:
    try:
        return await netplay_socket_handler.socket_server.get_session(sid) or {}
    except KeyError:
        return {}


async def _save_session(sid: str, **values: Any) -> None:
    session = await _get_session(sid)
    session.update(values)
    await netplay_socket_handler.socket_server.save_session(sid, session)


async def _clear_room_session(sid: str) -> None:
    session = await _get_session(sid)
    session.pop(ROOM_SESSION_KEY, None)
    session.pop(PLAYER_SESSION_KEY, None)
    await netplay_socket_handler.socket_server.save_session(sid, session)


async def _authenticated_user(sid: str) -> User | None:
    """The connect-time user, reloaded per call so a disable lands without a reconnect."""
    user_id = (await _get_session(sid)).get(AUTH_USER_SESSION_KEY)
    if user_id is None:
        return None

    user = db_user_handler.get_user(int(user_id))
    if not user or not user.enabled:
        return None
    return user


def _may_play(user: User | None, game_id: str | None) -> bool:
    """The gate the ROM endpoints apply, so a hidden ROM cannot be played here either."""
    if user is None or Scope.ROMS_READ not in user.oauth_scopes:
        return False

    try:
        rom_id = int(game_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False

    rom = db_rom_handler.get_rom_visibility(rom_id)
    if rom is None:
        return False
    return resolve_permissions(user).can_see_rom(rom.id, rom.platform_id)


@netplay_socket_handler.socket_server.on("connect")  # type: ignore
async def connect(sid: str, environ: dict[str, Any], auth: Any = None) -> None:
    """Never refuses, since the guest path needs ``join-room``, and stores identity from the session rather than the payload."""
    try:
        session = await get_session_from_environ(environ)
        if session.get("iss") != "romm:auth":
            return

        username = session.get("sub")
        if not username:
            return

        user = db_user_handler.get_user_by_username(username)
        if not user or not user.enabled:
            return

        await _save_session(sid, **{AUTH_USER_SESSION_KEY: user.id})
    except Exception:  # noqa: BLE001 - never let auth resolution refuse a socket
        log.exception("Failed to resolve user on netplay connect")


@netplay_socket_handler.socket_server.on("open-room")  # type: ignore
async def open_room(sid: str, data: RoomData):
    extra_data = data["extra"]

    session_id = extra_data.get("sessionid")
    player_id = extra_data.get("userid") or extra_data.get("playerId")

    if not session_id or not player_id:
        return "Invalid data: sessionId and playerId required"

    if not _may_play(await _authenticated_user(sid), extra_data.get("game_id")):
        log.warning("Netplay room creation rejected: not authorized for this rom")
        return "Not authorized to open a room for this game"

    if await netplay_handler.get(session_id):
        return "Room already exists"

    new_room = NetplayRoom(
        owner=sid,
        players={
            player_id: NetplayPlayerInfo(
                socketId=sid,
                player_name=extra_data.get("player_name") or f"Player {player_id}",
                userid=extra_data.get("userid"),
                playerId=extra_data.get("playerId"),
            )
        },
        peers=[],
        room_name=extra_data.get("room_name") or f"Room {session_id}",
        game_id=extra_data.get("game_id") or "default",
        domain=extra_data.get("domain", None),
        password=extra_data.get("room_password", None),
        max_players=data.get("maxPlayers") or DEFAULT_MAX_PLAYERS,
    )
    await netplay_handler.set(session_id, new_room)

    await netplay_socket_handler.socket_server.enter_room(sid, session_id)
    await _save_session(
        sid, **{ROOM_SESSION_KEY: session_id, PLAYER_SESSION_KEY: player_id}
    )
    await netplay_socket_handler.socket_server.emit(
        "users-updated", new_room["players"], room=session_id
    )


@netplay_socket_handler.socket_server.on("join-room")  # type: ignore
async def join_room(sid: str, data: RoomData):
    extra_data = data["extra"]

    session_id = extra_data.get("sessionid")
    player_id = extra_data.get("userid") or extra_data.get("playerId")

    if not session_id or not player_id:
        return "Invalid data: sessionId and playerId required"

    current_room = await netplay_handler.get(session_id)
    if not current_room:
        return "Room not found"

    password = current_room["password"]
    invited = bool(password) and password == extra_data.get("room_password")
    if password and not invited:
        return "Incorrect password"

    if not invited and not _may_play(
        await _authenticated_user(sid), current_room["game_id"]
    ):
        log.warning("Netplay join rejected: not authorized for this rom")
        return "Not authorized to join this room"

    if len(current_room["players"].keys()) >= current_room["max_players"]:
        return "Room is full"

    current_room["players"][player_id] = NetplayPlayerInfo(
        socketId=sid,
        player_name=extra_data.get("player_name") or f"Player {player_id}",
        userid=extra_data.get("userid"),
        playerId=extra_data.get("playerId"),
    )
    await netplay_handler.set(session_id, current_room)

    await netplay_socket_handler.socket_server.enter_room(sid, session_id)
    await _save_session(
        sid, **{ROOM_SESSION_KEY: session_id, PLAYER_SESSION_KEY: player_id}
    )
    await netplay_socket_handler.socket_server.emit(
        "users-updated", current_room["players"], room=session_id
    )

    return None, current_room["players"]


async def _room_peer_socket_ids(sid: str) -> set[str]:
    """The socket ids of the peers in the caller's room, empty if the caller is not one."""
    session_id = (await _get_session(sid)).get(ROOM_SESSION_KEY)
    if not session_id:
        return set()

    room = await netplay_handler.get(session_id)
    if not room:
        return set()

    peers = {player["socketId"] for player in room["players"].values()}
    return peers if sid in peers else set()


async def _handle_leave(sid: str, session_id: str, player_id: str):
    current_room = await netplay_handler.get(session_id)
    if not current_room:
        return

    current_room["players"].pop(player_id, None)

    if not current_room["players"]:
        await netplay_handler.delete([session_id])
        # Notify clients that the room is now empty
        await netplay_socket_handler.socket_server.emit(
            "users-updated", {}, room=session_id
        )
        return

    if sid == current_room["owner"]:
        # Owner left, assign a new one
        remaining_players = list(current_room["players"].values())
        if remaining_players:
            current_room["owner"] = remaining_players[0]["socketId"]

    await netplay_handler.set(session_id, current_room)
    await netplay_socket_handler.socket_server.emit(
        "users-updated", current_room["players"], room=session_id
    )


@netplay_socket_handler.socket_server.on("leave-room")  # type: ignore
async def leave_room(sid: str):
    stored_session = await _get_session(sid)
    session_id = stored_session.get(ROOM_SESSION_KEY)
    player_id = stored_session.get(PLAYER_SESSION_KEY)

    if session_id and player_id:
        await _handle_leave(sid, session_id, player_id)
        await netplay_socket_handler.socket_server.leave_room(sid, session_id)
        await _clear_room_session(sid)


@netplay_socket_handler.socket_server.on("webrtc-signal")  # type: ignore
async def webrtc_signal(sid: str, data: WebRTCSignalData):
    target = data.get("target")
    if not target:
        return  # drop message, no recipient

    # Signals relay only between peers of one room, so a client cannot inject an
    # offer or answer into a session it never joined.
    if target not in await _room_peer_socket_ids(sid):
        log.warning("Netplay signal to a non-peer rejected")
        return

    if data.get("requestRenegotiate", False):
        await netplay_socket_handler.socket_server.emit(
            "webrtc-signal",
            {"sender": sid, "requestRenegotiate": True},
            to=target,
        )
    else:
        await netplay_socket_handler.socket_server.emit(
            "webrtc-signal",
            {
                "sender": sid,
                "candidate": data.get("candidate"),
                "offer": data.get("offer"),
                "answer": data.get("answer"),
            },
            to=target,
        )


@netplay_socket_handler.socket_server.on("webrtc-signal-error")  # type: ignore
async def webrtc_signal_error(_sid: str, _error: str, _data: Any):
    pass


@netplay_socket_handler.socket_server.on("disconnect")  # type: ignore
async def disconnect(sid: str):
    stored_session = await _get_session(sid)
    session_id = stored_session.get(ROOM_SESSION_KEY)
    player_id = stored_session.get(PLAYER_SESSION_KEY)

    if session_id and player_id:
        await _handle_leave(sid, session_id, player_id)


async def _broadcast_to_room(sid: str, event: str, data: Any):
    session_id = (await _get_session(sid)).get(ROOM_SESSION_KEY)
    if session_id:
        await netplay_socket_handler.socket_server.emit(
            event, data, room=session_id, skip_sid=sid
        )


@netplay_socket_handler.socket_server.on("data-message")  # type: ignore
async def data_message(sid: str, data: Any):
    await _broadcast_to_room(sid, "data-message", data)


@netplay_socket_handler.socket_server.on("snapshot")  # type: ignore
async def snapshot(sid: str, data: Any):
    await _broadcast_to_room(sid, "snapshot", data)


@netplay_socket_handler.socket_server.on("input")  # type: ignore
async def input(sid: str, data: Any):
    await _broadcast_to_room(sid, "input", data)
