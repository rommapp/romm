"""Consoles RomM reaches over the network to sync saves with, set up from Settings."""

import uuid
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated

from fastapi import HTTPException, Request, status
from pydantic import AfterValidator, BaseModel, IPvAnyAddress, StringConstraints

from decorators.auth import protected_route
from endpoints.responses.device import DeviceSchema, PS3ProbeResponse
from endpoints.responses.sync import SyncSessionSchema
from handler.auth.constants import Scope
from handler.database import db_device_handler
from handler.sync.ps3.console import (
    PS3_DEVICE_TYPE,
    FtpPort,
    KeepVersions,
    PollIntervalMinutes,
    PS3SyncConfig,
    PS3User,
    is_ps3,
    probe_ps3,
)
from handler.sync.ps3.sync_handler import enqueue_ps3_sync
from logger.logger import log
from models.device import Device
from utils.router import APIRouter

router = APIRouter(prefix="/consoles")


def _local_address(
    address: IPv4Address | IPv6Address,
) -> IPv4Address | IPv6Address:
    # A console sits on the local network; anything else would turn RomM into
    # a client for hosts its users could not otherwise reach.
    if not (address.is_private or address.is_link_local) or address.is_loopback:
        raise ValueError("Must be an address on the local network")
    return address


LocalAddress = Annotated[IPvAnyAddress, AfterValidator(_local_address)]
ConsoleName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class PS3ConsoleCreatePayload(PS3SyncConfig):
    name: ConsoleName
    ip_address: LocalAddress


class PS3ConsoleUpdatePayload(BaseModel):
    name: ConsoleName | None = None
    ip_address: LocalAddress | None = None
    ftp_port: FtpPort | None = None
    ps3_user: PS3User | None = None
    poll_interval_minutes: PollIntervalMinutes | None = None
    keep_versions: KeepVersions | None = None


class PS3ProbePayload(BaseModel):
    ip_address: LocalAddress
    ftp_port: FtpPort = 21


def _owned_ps3_or_404(request: Request, device_id: str) -> Device:
    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device or not is_ps3(device):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PS3 console with ID {device_id} not found",
        )
    return device


@protected_route(
    router.post, "/ps3", [Scope.DEVICES_WRITE], status_code=status.HTTP_201_CREATED
)
def add_ps3_console(request: Request, payload: PS3ConsoleCreatePayload) -> DeviceSchema:
    """Set up a PS3 to sync saves with over FTP."""
    config = PS3SyncConfig.model_validate(
        payload.model_dump(include=set(PS3SyncConfig.model_fields))
    )
    device = db_device_handler.add_device(
        Device(
            id=str(uuid.uuid4()),
            user_id=request.user.id,
            name=payload.name,
            platform=PS3_DEVICE_TYPE.platform,
            client=PS3_DEVICE_TYPE.client,
            ip_address=str(payload.ip_address),
            sync_mode=PS3_DEVICE_TYPE.sync_mode,
            sync_enabled=True,
            sync_config=config.model_dump(),
            last_seen=None,
        )
    )
    log.info(f"Added PS3 console {device.id} for user {request.user.username}")
    return DeviceSchema.model_validate(device)


@protected_route(router.put, "/ps3/{device_id}", [Scope.DEVICES_WRITE])
def update_ps3_console(
    request: Request, device_id: str, payload: PS3ConsoleUpdatePayload
) -> DeviceSchema:
    """Change a PS3's address or sync settings."""
    device = _owned_ps3_or_404(request, device_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)

    data: dict[str, object] = {}
    if "name" in changes:
        data["name"] = changes.pop("name")
    if "ip_address" in changes:
        data["ip_address"] = str(changes.pop("ip_address"))
    if changes:
        config = PS3SyncConfig.of(device.sync_config).model_copy(update=changes)
        data["sync_config"] = config.model_dump()

    if data:
        updated = db_device_handler.update_device(
            device_id=device.id, user_id=request.user.id, data=data
        )
        device = updated or device
    return DeviceSchema.model_validate(device)


@protected_route(router.post, "/ps3/probe", [Scope.DEVICES_WRITE])
async def probe_ps3_console(
    request: Request, payload: PS3ProbePayload
) -> PS3ProbeResponse:
    """Check that a PS3's FTP server answers, and list its user profiles."""
    result = await probe_ps3(str(payload.ip_address), payload.ftp_port)
    return PS3ProbeResponse(
        reachable=result.reachable, is_ftp=result.is_ftp, users=result.users
    )


@protected_route(router.post, "/ps3/{device_id}/sync", [Scope.DEVICES_WRITE])
def sync_ps3_console(request: Request, device_id: str) -> SyncSessionSchema:
    """Sync a PS3 now, whatever its interval."""
    device = _owned_ps3_or_404(request, device_id)
    if not device.sync_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sync is disabled for this console",
        )
    sync_session = enqueue_ps3_sync(device)
    log.info(f"Queued PS3 sync session {sync_session.id} for device {device.id}")
    return SyncSessionSchema.model_validate(sync_session)
