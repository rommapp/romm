import json
from typing import Optional, TypedDict

from handler.redis_handler import async_cache


class NetplayPlayerInfo(TypedDict):
    socketId: str
    player_name: str
    userid: str | None
    playerId: str | None


class NetplayRoom(TypedDict):
    owner: str
    players: dict[str, NetplayPlayerInfo]
    peers: list[str]
    room_name: str
    game_id: str
    domain: Optional[str]
    password: Optional[str]
    max_players: int


class NetplayHandler:
    """A class to handle netplay rooms in Redis."""

    def __init__(self):
        self.hash_name = "netplay:rooms"

    async def get(self, room_id: str) -> NetplayRoom | None:
        """Get a room from Redis."""
        room = await async_cache.hget(self.hash_name, room_id)
        return json.loads(room) if room else None

    def set(self, room_id: str, room_data: NetplayRoom):
        """Set a room in Redis."""
        return async_cache.hset(self.hash_name, room_id, json.dumps(room_data))

    def delete(self, room_id: str):
        """Delete a room from Redis."""
        return async_cache.hdel(self.hash_name, room_id)

    async def get_all(self) -> dict[str, NetplayRoom]:
        """Get all rooms from Redis."""
        rooms = await async_cache.hgetall(self.hash_name)
        return {room_id: json.loads(room_data) for room_id, room_data in rooms.items()}


netplay_handler = NetplayHandler()
