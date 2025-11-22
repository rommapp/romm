from typing import Dict, Optional, TypedDict

from fastapi import HTTPException, Request, status

from decorators.auth import protected_route
from handler.auth.constants import Scope
from utils.router import APIRouter

router = APIRouter(
    prefix="/netplay",
    tags=["netplay"],
)


class NetplayPlayerInfo(TypedDict):
    socket_id: str
    player_name: str
    user_id: str | None
    player_id: str | None


class NetplayRoom(TypedDict):
    owner: str
    players: Dict[str, NetplayPlayerInfo]
    peers: list[str]
    room_name: str
    game_id: str
    domain: Optional[str]
    password: Optional[str]
    max_players: int


netplay_rooms: dict[str, NetplayRoom] = {}

# # Background cleanup task to delete empty rooms periodically
# async def cleanup_empty_rooms_loop():
#     while True:
#         await asyncio.sleep(60)
#         to_delete = [sid for sid, r in rooms.items() if len(r.get("players", {})) == 0]
#         for sid in to_delete:
#             del rooms[sid]


# # Start cleanup task on app startup
# @app.on_event("startup")
# async def startup_event():
#     asyncio.create_task(cleanup_empty_rooms_loop())


DEFAULT_MAX_PLAYERS = 4


def _get_owner_player_name(room: NetplayRoom) -> str:
    owner_sid = room["owner"]
    if not owner_sid:
        return "Unknown"

    for _pid, p in room["players"].items():
        if p["socket_id"] == owner_sid:
            return p["player_name"]

    return "Unknown"


def _is_room_open(room: NetplayRoom, game_id: str) -> bool:
    if len(room["players"]) >= room["max_players"]:
        return False
    return str(room["game_id"]) == str(game_id)


class RoomsResponse(TypedDict):
    room_name: str
    current: int
    max: int
    player_name: str
    hasPassword: bool


@protected_route(router.get, "/list", [Scope.ASSETS_READ])
def get_rooms(request: Request, game_id: Optional[str]) -> Dict[str, RoomsResponse]:
    if not game_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing game_id query parameter",
        )

    open_rooms: Dict[str, RoomsResponse] = {}
    for session_id, room in netplay_rooms.items():
        if not _is_room_open(room, game_id):
            continue

        open_rooms[session_id] = RoomsResponse(
            room_name=room["room_name"],
            current=len(room["players"]),
            max=room["max_players"],
            player_name=_get_owner_player_name(room),
            hasPassword=bool(room["password"]),
        )

    return open_rooms
