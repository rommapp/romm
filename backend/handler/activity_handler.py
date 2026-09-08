"""Real-time user game activity tracking.

Stores ephemeral "currently playing" state in Redis. Each active session is a
Redis key with a short TTL, refreshed by periodic heartbeats from the client
(browser) or the device. When the TTL expires (no heartbeat received), the
session is considered ended automatically.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, TypedDict

from endpoints.responses.activity import ActivityClearSchema
from handler.database import (
    db_device_handler,
    db_rom_handler,
    db_save_handler,
    db_user_handler,
)
from handler.redis_handler import async_cache
from handler.socket_handler import socket_handler
from logger.logger import log
from utils.screenshots import continue_playing_screenshot


class ActivityEntry(TypedDict):
    user_id: int
    username: str
    avatar_path: str
    rom_id: int
    rom_name: str
    rom_cover_path: str  # small cover path, may be empty
    screenshot_path: str  # "where they are" image (save/title/screenshot), may be empty
    platform_slug: str
    platform_name: str
    device_id: str
    device_type: str  # "web", "grout", "argosy-launcher", "streaming", etc.
    started_at: str  # ISO 8601 timestamp


class ActivityHandler:
    """Redis-backed store for currently active game play sessions."""

    ACTIVITY_TTL = 90  # seconds; refreshed by heartbeats
    ROM_INDEX_TTL = 120  # slightly longer than ACTIVITY_TTL
    KEY_PREFIX = "activity:user:"
    ROM_INDEX_PREFIX = "activity:rom:"

    def _activity_key(self, user_id: int, device_id: str) -> str:
        return f"{self.KEY_PREFIX}{user_id}:{device_id}"

    def _rom_index_key(self, rom_id: int) -> str:
        return f"{self.ROM_INDEX_PREFIX}{rom_id}"

    def _member(self, user_id: int, device_id: str) -> str:
        return f"{user_id}:{device_id}"

    async def build_entry(
        self,
        *,
        user_id: int,
        device_id: str,
        rom_id: int,
        preserve_started_at: bool,
        device_type: str | None = None,
    ) -> ActivityEntry | None:
        """Assemble an entry from the database, or None if the user or ROM is gone.

        Args:
            preserve_started_at: keep the start time of the entry already
                stored, so refreshing does not reset the elapsed label.
            device_type: what is being played on, for callers with no registered
                device to read it from. Looked up from the device when omitted.
        """
        user = db_user_handler.get_user(user_id)
        if user is None:
            log.debug(f"activity: unknown user_id {user_id}")
            return None

        rom = db_rom_handler.get_rom(rom_id)
        if rom is None:
            log.debug(f"activity: unknown rom_id {rom_id}")
            return None

        started_at = datetime.now(timezone.utc).isoformat()
        if preserve_started_at:
            existing = await self.get_active(user_id, device_id)
            if existing:
                started_at = existing["started_at"]

        if device_type is None:
            device = db_device_handler.get_device(device_id=device_id, user_id=user_id)
            device_type = device.client if device else None

        # "Where they are" image - the player's latest save screenshot, else the
        # title screen / first gameplay screenshot (frontend falls back to cover).
        latest_save = db_save_handler.get_latest_saves_for_roms(
            user_id=user_id, rom_ids=[rom_id]
        ).get(rom_id)

        platform = rom.platform
        return ActivityEntry(
            user_id=user.id,
            username=user.username,
            avatar_path=user.avatar_path or "",
            rom_id=rom.id,
            rom_name=rom.name or rom.fs_name,
            rom_cover_path=rom.path_cover_s or "",
            screenshot_path=continue_playing_screenshot(rom, latest_save) or "",
            platform_slug=platform.slug if platform else "",
            platform_name=((platform.custom_name or platform.name) if platform else ""),
            device_id=device_id,
            device_type=device_type or "web",
            started_at=started_at,
        )

    async def publish_active(self, entry: ActivityEntry) -> None:
        """Store a session and broadcast it to every connected client."""
        await self.set_active(entry)
        await self._broadcast("activity:update", dict(entry))

    async def publish_clear(self, user_id: int, device_id: str) -> int | None:
        """End a session and broadcast it. Returns the rom_id cleared, if any."""
        rom_id = await self.clear_active(user_id, device_id)
        if rom_id is None:
            return None
        await self._broadcast(
            "activity:clear",
            ActivityClearSchema(
                user_id=user_id, device_id=device_id, rom_id=rom_id
            ).model_dump(),
        )
        return rom_id

    async def _broadcast(self, event: str, payload: dict[str, Any]) -> None:
        # The REST app shares this process with the Socket.IO server, so emit
        # through the already-initialised, Redis-backed server (it fans out
        # across workers) rather than opening a manager per call.
        try:
            await socket_handler.socket_server.emit(event, payload)
        except Exception as e:  # noqa: BLE001
            log.warning(f"Failed to broadcast {event}: {e}")

    async def set_active(self, entry: ActivityEntry) -> None:
        """Store or refresh a user's active play session."""
        key = self._activity_key(entry["user_id"], entry["device_id"])
        rom_key = self._rom_index_key(entry["rom_id"])
        member = self._member(entry["user_id"], entry["device_id"])

        async with async_cache.pipeline() as pipe:
            await pipe.set(key, json.dumps(entry), ex=self.ACTIVITY_TTL)
            await pipe.sadd(rom_key, member)
            await pipe.expire(rom_key, self.ROM_INDEX_TTL)
            await pipe.execute()

    async def clear_active(self, user_id: int, device_id: str) -> int | None:
        """Clear a user's active play session. Returns the rom_id that was cleared, or None."""
        key = self._activity_key(user_id, device_id)
        raw = await async_cache.get(key)
        if not raw:
            return None

        try:
            entry = json.loads(raw)
            rom_id = int(entry["rom_id"])
        except (ValueError, KeyError, TypeError) as e:
            log.warning(f"Failed to parse activity entry for cleanup: {e}")
            await async_cache.delete(key)
            return None

        member = self._member(user_id, device_id)
        async with async_cache.pipeline() as pipe:
            await pipe.delete(key)
            await pipe.srem(self._rom_index_key(rom_id), member)
            await pipe.execute()
        return rom_id

    async def get_active(self, user_id: int, device_id: str) -> ActivityEntry | None:
        """Get a single active session by user and device."""
        key = self._activity_key(user_id, device_id)
        raw = await async_cache.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            return None

    async def get_all_active(self) -> list[ActivityEntry]:
        """Get all currently active play sessions across all users."""
        pattern = f"{self.KEY_PREFIX}*"
        keys = [key async for key in async_cache.scan_iter(match=pattern)]
        if not keys:
            return []

        # Single round-trip for every value instead of a GET per key.
        entries: list[ActivityEntry] = []
        for raw in await async_cache.mget(keys):
            if not raw:
                continue
            try:
                entries.append(json.loads(raw))
            except ValueError:
                continue
        return entries

    async def get_active_for_rom(self, rom_id: int) -> list[ActivityEntry]:
        """Get all active play sessions for a specific ROM."""
        rom_key = self._rom_index_key(rom_id)
        members = await async_cache.smembers(rom_key)
        entries: list[ActivityEntry] = []
        stale_members: list[str] = []

        for member in members:
            try:
                user_id_str, device_id = member.rsplit(":", 1)
                user_id = int(user_id_str)
            except (ValueError, AttributeError):
                stale_members.append(member)
                continue

            raw = await async_cache.get(self._activity_key(user_id, device_id))
            if not raw:
                # Key expired; clean up the stale set member.
                stale_members.append(member)
                continue
            try:
                entries.append(json.loads(raw))
            except ValueError:
                stale_members.append(member)

        if stale_members:
            await async_cache.srem(rom_key, *stale_members)

        return entries


activity_handler = ActivityHandler()
