"""Install requests a user pushes to one of their devices, held in Redis while live."""

import uuid
from datetime import datetime, timezone
from typing import Final, NamedTuple

from redis.asyncio import Redis
from redis.asyncio.client import Pipeline
from redis.exceptions import WatchError

from config import DEVICE_INSTALL_REQUEST_TTL_DAYS
from endpoints.responses.device_install import InstallRequestSchema, InstallStatus
from handler.redis_handler import as_text, async_cache
from logger.logger import log

TRANSACTION_ATTEMPTS: Final = 3
REPORTABLE_FROM: Final = frozenset({InstallStatus.TAKEN})
CANCELLABLE_FROM: Final = frozenset({InstallStatus.PENDING, InstallStatus.TAKEN})


class InstallTransitionError(Exception):
    """The request is not in the status the operation needs, or kept changing."""


class InstallClaim(NamedTuple):
    """Every request the device holds taken, oldest first, and those this claim took."""

    taken: list[InstallRequestSchema]
    newly_taken: list[InstallRequestSchema]


def _oldest_first(
    requests: list[InstallRequestSchema],
) -> list[InstallRequestSchema]:
    return sorted(requests, key=lambda request: request.created_at)


def _claim(
    already_taken: list[InstallRequestSchema], newly_taken: list[InstallRequestSchema]
) -> InstallClaim:
    return InstallClaim(
        taken=_oldest_first(already_taken + newly_taken),
        newly_taken=_oldest_first(newly_taken),
    )


def _request_key(request_id: str) -> str:
    return f"install:req:{request_id}"


def _device_key(device_id: str) -> str:
    return f"install:device:{device_id}"


def _rom_key(user_id: int, rom_id: int) -> str:
    return f"install:rom:{user_id}:{rom_id}"


def _active_key(request: InstallRequestSchema) -> str:
    return f"install:active:{request.user_id}:{request.device_id}:{request.rom_id}"


class DeviceInstallHandler:
    def __init__(self, ttl_days: int = DEVICE_INSTALL_REQUEST_TTL_DAYS) -> None:
        self.ttl_seconds: int | None = ttl_days * 24 * 60 * 60 if ttl_days > 0 else None

    async def create(
        self,
        user_id: int,
        device_id: str,
        rom_id: int,
        file_ids: list[int],
    ) -> tuple[InstallRequestSchema, bool]:
        """The live request for the rom on the device, and whether this call queued it.

        Raises:
            InstallTransitionError: Concurrent creates kept colliding.
        """
        now = datetime.now(timezone.utc)
        request = InstallRequestSchema(
            id=str(uuid.uuid4()),
            user_id=user_id,
            device_id=device_id,
            rom_id=rom_id,
            file_ids=file_ids,
            status=InstallStatus.PENDING,
            reason=None,
            created_at=now,
            updated_at=now,
        )
        active_key = _active_key(request)
        async with async_cache.pipeline(transaction=True) as pipe:
            for _ in range(TRANSACTION_ATTEMPTS):
                try:
                    await pipe.watch(active_key)
                    active_id = await pipe.get(active_key)
                    if active_id is not None:
                        [existing] = await self._read(pipe, [as_text(active_id)])
                        if existing is not None:
                            return existing, False

                    pipe.multi()
                    self._stage_write(pipe, request, owns_active_key=True)
                    await pipe.execute()
                    return request, True
                except WatchError:
                    continue
        raise InstallTransitionError(
            "Another request for this rom was queued at the same time"
        )

    async def get(self, request_id: str) -> InstallRequestSchema | None:
        [request] = await self._read(async_cache, [request_id])
        return request

    async def list_for_device(self, device_id: str) -> list[InstallRequestSchema]:
        """The device's live requests, oldest first."""
        return await self._load(_device_key(device_id))

    async def list_for_rom(
        self, user_id: int, rom_id: int
    ) -> list[InstallRequestSchema]:
        """Every live request the user made for a rom, oldest first."""
        return await self._load(_rom_key(user_id, rom_id))

    async def claim(self, device_id: str) -> InstallClaim:
        """Take every pending request of the device, returning all it holds taken.

        Raises:
            InstallTransitionError: Other writers kept changing the requests.
        """
        device_key = _device_key(device_id)
        async with async_cache.pipeline(transaction=True) as pipe:
            for _ in range(TRANSACTION_ATTEMPTS):
                try:
                    await pipe.watch(device_key)
                    ids = [as_text(i) for i in await pipe.smembers(device_key)]
                    if ids:
                        await pipe.watch(*[_request_key(i) for i in ids])
                    stored = await self._read(pipe, ids)
                    gone = [
                        request_id
                        for request_id, request in zip(ids, stored, strict=True)
                        if request is None
                    ]
                    live = [request for request in stored if request is not None]
                    already_taken = [
                        request
                        for request in live
                        if request.status == InstallStatus.TAKEN
                    ]
                    pending = [
                        request
                        for request in live
                        if request.status == InstallStatus.PENDING
                    ]
                    owned = (
                        await self._owns_active_keys(pipe, pending) if pending else []
                    )
                    now = datetime.now(timezone.utc)
                    taken = [
                        request.model_copy(
                            update={"status": InstallStatus.TAKEN, "updated_at": now}
                        )
                        for request in pending
                    ]
                    if gone or taken:
                        pipe.multi()
                        if gone:
                            pipe.srem(device_key, *gone)
                        for request, owns_active_key in zip(taken, owned, strict=True):
                            self._stage_write(pipe, request, owns_active_key)
                        await pipe.execute()
                    return _claim(already_taken, taken)
                except WatchError:
                    continue
        raise InstallTransitionError(
            "The device's requests kept changing while they were being claimed"
        )

    async def report(
        self, request_id: str, outcome: InstallStatus, reason: str | None
    ) -> InstallRequestSchema:
        """End a taken request with the device's outcome, returning it as it ended.

        Raises:
            KeyError: The request is gone.
            InstallTransitionError: The request is not taken.
        """
        return await self._end(request_id, outcome, REPORTABLE_FROM, reason)

    async def cancel(self, request_id: str) -> InstallRequestSchema:
        """End a pending or taken request as cancelled, returning it as it ended.

        Raises:
            KeyError: The request is gone.
            InstallTransitionError: The request kept changing.
        """
        return await self._end(
            request_id, InstallStatus.CANCELLED, CANCELLABLE_FROM, None
        )

    async def discard_for_device(self, device_id: str) -> None:
        """Drop a deleted device's live requests and their index, logging a failure."""
        try:
            requests = await self.list_for_device(device_id)
            async with async_cache.pipeline(transaction=True) as pipe:
                for request in requests:
                    self._stage_delete(pipe, request, owns_active_key=True)
                pipe.delete(_device_key(device_id))
                await pipe.execute()
        except Exception:  # noqa: BLE001
            log.warning(
                f"Failed to drop the install requests of device {device_id}",
                exc_info=True,
            )

    async def _end(
        self,
        request_id: str,
        status: InstallStatus,
        from_statuses: frozenset[InstallStatus],
        reason: str | None,
    ) -> InstallRequestSchema:
        key = _request_key(request_id)
        async with async_cache.pipeline(transaction=True) as pipe:
            for _ in range(TRANSACTION_ATTEMPTS):
                try:
                    await pipe.watch(key)
                    [current] = await self._read(pipe, [request_id])
                    if current is None:
                        raise KeyError(request_id)
                    if current.status not in from_statuses:
                        raise InstallTransitionError(
                            f"Cannot move a {current.status} request to {status}"
                        )

                    [owns_active_key] = await self._owns_active_keys(pipe, [current])
                    pipe.multi()
                    self._stage_delete(pipe, current, owns_active_key)
                    await pipe.execute()
                    return current.model_copy(
                        update={
                            "status": status,
                            "reason": reason,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )
                except WatchError:
                    continue
        raise InstallTransitionError("The request kept changing while it was ended")

    async def _read(
        self, client: Redis[str], request_ids: list[str]
    ) -> list[InstallRequestSchema | None]:
        """The stored requests in ``request_ids`` order, None where one is gone."""
        if not request_ids:
            return []
        stored = await client.mget([_request_key(i) for i in request_ids])
        return [
            InstallRequestSchema.model_validate_json(raw) if raw else None
            for raw in stored
        ]

    async def _load(self, set_key: str) -> list[InstallRequestSchema]:
        ids = [as_text(i) for i in await async_cache.smembers(set_key)]
        stored = await self._read(async_cache, ids)
        gone = [
            request_id
            for request_id, request in zip(ids, stored, strict=True)
            if request is None
        ]
        if gone:
            await async_cache.srem(set_key, *gone)
        return _oldest_first([request for request in stored if request is not None])

    async def _owns_active_keys(
        self, pipe: Pipeline[str], requests: list[InstallRequestSchema]
    ) -> list[bool]:
        """Whether each rom's dedupe key still names its request, watching the keys."""
        active_keys = [_active_key(request) for request in requests]
        await pipe.watch(*active_keys)
        active_ids = await pipe.mget(active_keys)
        return [
            active_id is not None and as_text(active_id) == request.id
            for request, active_id in zip(requests, active_ids, strict=True)
        ]

    def _stage_write(
        self, pipe: Pipeline[str], request: InstallRequestSchema, owns_active_key: bool
    ) -> None:
        """Queue the request's write; each index lives as long as its newest request."""
        device_key = _device_key(request.device_id)
        rom_key = _rom_key(request.user_id, request.rom_id)
        pipe.set(
            _request_key(request.id), request.model_dump_json(), ex=self.ttl_seconds
        )
        pipe.sadd(device_key, request.id)
        pipe.sadd(rom_key, request.id)
        if owns_active_key:
            pipe.set(_active_key(request), request.id, ex=self.ttl_seconds)
        if self.ttl_seconds is not None:
            pipe.expire(device_key, self.ttl_seconds)
            pipe.expire(rom_key, self.ttl_seconds)

    def _stage_delete(
        self, pipe: Pipeline[str], request: InstallRequestSchema, owns_active_key: bool
    ) -> None:
        pipe.delete(_request_key(request.id))
        pipe.srem(_device_key(request.device_id), request.id)
        pipe.srem(_rom_key(request.user_id, request.rom_id), request.id)
        if owns_active_key:
            pipe.delete(_active_key(request))


device_install_handler = DeviceInstallHandler()
