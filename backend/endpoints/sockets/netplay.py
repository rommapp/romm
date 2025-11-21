from typing import NotRequired, TypedDict

from endpoints.netplay import (
    DEFAULT_MAX_PLAYERS,
    NetplayPlayerInfo,
    NetplayRoom,
    netplay_rooms,
)
from handler.socket_handler import socket_handler


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


@socket_handler.socket_server.on("open-room")  # type: ignore
async def open_room(sid: str, data: RoomData):
    extra_data = data["extra"]

    session_id = extra_data["sessionid"]
    player_id = extra_data["userid"] or extra_data["playerId"]

    if not session_id or not player_id:
        return "Invalid data: sessionId and playerId required"

    if session_id in netplay_rooms:
        return "Room already exists"

    netplay_rooms[session_id] = NetplayRoom(
        owner=sid,
        players={
            player_id: NetplayPlayerInfo(
                socket_id=sid,
                player_name=extra_data.get("player_name") or f"Player {player_id}",
                user_id=extra_data.get("userid"),
                player_id=extra_data.get("playerId"),
            )
        },
        peers=[],
        room_name=extra_data.get("room_name") or f"Room {session_id}",
        game_id=extra_data.get("game_id") or "default",
        domain=extra_data.get("domain", None),
        password=extra_data.get("room_password", None),
        max_players=data.get("maxPlayers") or DEFAULT_MAX_PLAYERS,
    )

    stored_session = await socket_handler.socket_server.get_session(sid)
    await socket_handler.socket_server.enter_room(sid, session_id)
    await socket_handler.socket_server.save_session(
        sid,
        {
            "session_id": session_id,
            "player_id": player_id,
            "environ": stored_session.get("environ"),
        },
    )
    await socket_handler.socket_server.emit(
        "users-updated", netplay_rooms[session_id]["players"], room=session_id
    )

    return None


@socket_handler.socket_server.on("join-room")  # type: ignore
async def join_room(sid: str, data: RoomData):
    extra_data = data["extra"]

    session_id = extra_data["sessionid"]
    player_id = extra_data["userid"] or extra_data["playerId"]

    if not session_id or not player_id:
        return "Invalid data: sessionId and playerId required"

    if session_id not in netplay_rooms:
        return "Room not found"

    room = netplay_rooms[session_id]
    if room["password"] and room["password"] != extra_data.get("room_password"):
        return "Incorrect password"

    if len(room["players"].keys()) >= room["max_players"]:
        return "Room is full"

    room["players"][player_id] = NetplayPlayerInfo(
        socket_id=sid,
        player_name=extra_data.get("player_name") or f"Player {player_id}",
        user_id=extra_data.get("userid"),
        player_id=extra_data.get("playerId"),
    )

    stored_session = await socket_handler.socket_server.get_session(sid)
    await socket_handler.socket_server.enter_room(sid, session_id)
    await socket_handler.socket_server.save_session(
        sid,
        {
            "session_id": session_id,
            "player_id": player_id,
            "environ": stored_session.get("environ"),
        },
    )
    await socket_handler.socket_server.emit("users-updated", room["players"])
