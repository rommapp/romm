from typing import Dict, TypedDict

from fastapi import Request

from decorators.auth import protected_route
from handler.auth.constants import Scope
from handler.netplay_handler import NetplayRoom, netplay_handler
from utils.router import APIRouter

router = APIRouter(
    prefix="/netplay",
    tags=["netplay"],
)


DEFAULT_MAX_PLAYERS = 4


def _get_owner_player_name(room: NetplayRoom) -> str:
    owner_sid = room.get("owner")
    if not owner_sid:
        return "Unknown"

    return next(
        (
            p["player_name"]
            for p in room["players"].values()
            if p["socketId"] == owner_sid
        ),
        "Unknown",
    )


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
async def get_rooms(request: Request, game_id: str) -> Dict[str, RoomsResponse]:
    netplay_rooms = await netplay_handler.get_all()

    open_rooms: Dict[str, RoomsResponse] = {
        session_id: RoomsResponse(
            room_name=room["room_name"],
            current=len(room["players"]),
            max=room["max_players"],
            player_name=_get_owner_player_name(room),
            hasPassword=bool(room["password"]),
        )
        for session_id, room in netplay_rooms.items()
        if _is_room_open(room, game_id)
    }

    return open_rooms
