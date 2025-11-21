from typing import Any, Dict

from fastapi import HTTPException, Request, status

from decorators.auth import protected_route
from handler.auth.constants import Scope
from utils.router import APIRouter

router = APIRouter(
    prefix="/netplay",
    tags=["netplay"],
)

rooms: Dict[str, Dict[str, Any]] = {}

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


@protected_route(
    router.get,
    "/list",
    [Scope.ASSETS_READ],
)
def get_rooms(request: Request, game_id: str) -> Any:
    if game_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing game_id query parameter",
        )

    open_rooms = {}
    for session_id, room in rooms.items():
        if (
            room
            and len(room.get("players", {})) < room.get("maxPlayers", 4)
            and str(room.get("gameId", "")) == str(game_id)
        ):
            # find owner player id to extract player_name
            owner_sid = room.get("owner")
            owner_player_id = next(
                (
                    pid
                    for pid, p in room["players"].items()
                    if p.get("socketId") == owner_sid
                ),
                None,
            )
            player_name = (
                room["players"][owner_player_id].get("player_name")
                if owner_player_id
                else "Unknown"
            )
            open_rooms[session_id] = {
                "room_name": room.get("roomName"),
                "current": len(room.get("players", {})),
                "max": room.get("maxPlayers"),
                "player_name": player_name,
                "hasPassword": bool(room.get("password")),
            }
    return open_rooms
