from typing import NotRequired, TypedDict

import socketio  # type: ignore

from config import REDIS_URL
from endpoints.netplay import rooms
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


def _get_socket_manager() -> socketio.AsyncRedisManager:
    """Connect to external socketio server"""
    return socketio.AsyncRedisManager(REDIS_URL, write_only=True)


# if (!sessionId || !playerId) {
#   return callback('Invalid data: sessionId and playerId required');
# }
# if (rooms[sessionId]) {
#   return callback('Room already exists');
# }

# let finalDomain = data.extra.domain;
# if (finalDomain === undefined || finalDomain === null) {
#     finalDomain = 'unknown';
# }

# rooms[sessionId] = {
#   owner: socket.id,
#   players: { [playerId]: { ...data.extra, socketId: socket.id } },
#   peers: [],
#   roomName: roomName || `Room ${sessionId}`,
#   gameId: gameId || 'default',
#   domain: finalDomain,
#   password: data.password || null,
#   maxPlayers: maxPlayers,
# };
# socket.join(sessionId);
# socket.sessionId = sessionId;
# socket.playerId = playerId;
# io.to(sessionId).emit('users-updated', rooms[sessionId].players);
# callback(null);


@socket_handler.socket_server.on("open-room")  # type: ignore
async def open_room(sid: str, data: RoomData):
    extra_data = data["extra"]

    session_id = extra_data["sessionid"]
    player_id = extra_data["userid"] or extra_data["playerId"]

    if not session_id or not player_id:
        return "Invalid data: sessionId and playerId required"

    if session_id in rooms:
        return "Room already exists"

    rooms[session_id] = {
        "owner": sid,
        "players": {[player_id]: {**extra_data, "socket_id": sid}},
        "peers": [],
        "room_name": extra_data["room_name"] or f"Room {session_id}",
        "game_id": extra_data["game_id"] or "default",
        "domain": extra_data["domain"],
        "password": extra_data["room_password"],
        "max_players": data["maxPlayers"] or 4,
    }

    socket_handler.socket_server.enter_room(sid, session_id)
    socket_handler.socket_server.save_session(
        sid,
        {
            "session_id": session_id,
            "player_id": player_id,
            "environ": (await socket_handler.socket_server.get_session(sid)).get(
                "environ"
            ),
        },
    )
    socket_handler.socket_server.emit(
        "users-updated", rooms[session_id]["players"], room=session_id
    )

    return None


#   owner: socket.id,
#   players: { [playerId]: { ...data.extra, socketId: socket.id } },
#   peers: [],
#   roomName: roomName || `Room ${sessionId}`,
#   gameId: gameId || 'default',
#   domain: finalDomain,
#   password: data.password || null,
#   maxPlayers: maxPlayers,
# };
# socket.join(sessionId);
# socket.sessionId = sessionId;
# socket.playerId = playerId;
# io.to(sessionId).emit('users-updated', rooms[sessionId].players);
# callback(null);
