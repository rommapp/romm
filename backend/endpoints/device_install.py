"""Install requests: the web UI queues and cancels them, the device claims and reports them."""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Final

from fastapi import HTTPException
from fastapi import Path as PathVar
from fastapi import Request, Response, status
from pydantic import BaseModel, Field, field_validator

from config import DEVICE_INSTALL_ENABLED
from decorators.auth import protected_route
from endpoints.responses.device_install import (
    InstallReason,
    InstallRequestSchema,
    InstallStatus,
)
from endpoints.sockets.devices import (
    emit_install_cancelled,
    emit_install_queued,
    emit_install_updated,
)
from exceptions.endpoint_exceptions import (
    DeviceInstallDisabledException,
    RomNotFoundInDatabaseException,
)
from handler.auth.constants import Scope
from handler.auth.dependencies import assert_rom_visible
from handler.database import db_device_handler, db_rom_handler
from handler.device_install_handler import (
    InstallRequestNotFoundError,
    InstallTransitionError,
    device_install_handler,
)
from handler.device_install_policy import (
    InstallNotAllowedError,
    accepts_remote_install,
    is_installable_platform,
    select_install_files,
)
from handler.notification_handler import notify
from logger.logger import log
from models.device import Device
from models.notification import NotificationKind, NotificationLevel
from utils.router import APIRouter

router = APIRouter(
    prefix="/devices",
    tags=["devices"],
)

DEVICE_REPORTS: Final = frozenset(
    {InstallStatus.DONE, InstallStatus.ALREADY_INSTALLED, InstallStatus.FAILED}
)


class InstallRequestCreatePayload(BaseModel):
    rom_id: int = Field(ge=1)


class InstallRequestUpdatePayload(BaseModel):
    status: InstallStatus
    reason: InstallReason | None = None

    @field_validator("status")
    @classmethod
    def _reportable(cls, value: InstallStatus) -> InstallStatus:
        if value not in DEVICE_REPORTS:
            raise ValueError(
                f"A device reports one of {', '.join(sorted(DEVICE_REPORTS))}"
            )
        return value


def _require_device(
    request: Request, device_id: str, device_only: bool = False
) -> Device:
    """The caller's device, 404 when not theirs and 403 under ``device_only`` for another caller."""
    bound_device_id = getattr(request.state, "device_id", None)
    owned = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if owned is None or bound_device_id not in (None, device_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    if device_only and bound_device_id != device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the device itself can do this",
        )
    return owned


async def _require_request(request: Request, device_id: str, request_id: str) -> None:
    install = await device_install_handler.get(request_id)
    if (
        install is None
        or install.device_id != device_id
        or install.user_id != request.user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Install request {request_id} not found",
        )


@contextmanager
def _install_errors() -> Iterator[None]:
    """A gone request as a 404, a request in the wrong status as a 409."""
    try:
        yield
    except InstallRequestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Install request {exc.args[0]} not found",
        ) from exc
    except InstallTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


async def _notify_outcome(install: InstallRequestSchema, device: Device) -> None:
    rom = db_rom_handler.get_rom_visibility_label(install.rom_id)
    failed = install.status == InstallStatus.FAILED
    await notify(
        install.user_id,
        (
            NotificationKind.DEVICE_INSTALL_FAILED
            if failed
            else NotificationKind.DEVICE_INSTALL_COMPLETED
        ),
        NotificationLevel.ERROR if failed else NotificationLevel.SUCCESS,
        {
            "rom_id": install.rom_id,
            "rom_name": (rom.name or rom.fs_name) if rom else None,
            "device_name": device.name or device.hostname,
            "status": install.status,
            "reason": install.reason,
        },
    )


@protected_route(
    router.post,
    "/{device_id}/installs",
    [Scope.DEVICES_WRITE, Scope.ROMS_READ],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {"model": InstallRequestSchema},
        status.HTTP_400_BAD_REQUEST: {},
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_409_CONFLICT: {},
    },
)
async def create_install_request(
    request: Request,
    response: Response,
    device_id: Annotated[str, PathVar(description="Target device id.")],
    payload: InstallRequestCreatePayload,
) -> InstallRequestSchema:
    """Queue a rom for install on a device, returning a live request for the same pair with 200."""
    if not DEVICE_INSTALL_ENABLED:
        raise DeviceInstallDisabledException()
    device = _require_device(request, device_id)
    if not accepts_remote_install(device.capabilities):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Device {device_id} does not accept remote installs",
        )

    rom = db_rom_handler.get_rom_install_target(payload.rom_id)
    if not rom:
        raise RomNotFoundInDatabaseException(payload.rom_id)
    assert_rom_visible(request, rom)

    if not is_installable_platform(rom.platform_slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Roms for {rom.platform_slug} cannot be installed on a device",
        )
    # A rescan flags only the rom when its path is gone, never its file rows.
    files = [] if rom.missing_from_fs else db_rom_handler.rom_files_for_rom_id(rom.id)
    try:
        file_ids = select_install_files(files)
    except InstallNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    with _install_errors():
        install, created = await device_install_handler.create(
            user_id=request.user.id,
            device_id=device_id,
            rom_id=rom.id,
            file_ids=file_ids,
        )

    if not created:
        response.status_code = status.HTTP_200_OK
        return install

    # A delete that ran between the device check and the write missed this request.
    if (
        db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
        is None
    ):
        await device_install_handler.discard_for_device(device_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )

    log.info(f"Queued rom {rom.id} for install on device {device_id}")
    await asyncio.gather(emit_install_queued(install), emit_install_updated(install))
    return install


@protected_route(
    router.get,
    "/{device_id}/installs",
    [Scope.DEVICES_READ],
    responses={status.HTTP_404_NOT_FOUND: {}},
)
async def list_install_requests(
    request: Request,
    device_id: Annotated[str, PathVar(description="Target device id.")],
) -> list[InstallRequestSchema]:
    """The device's pending and taken requests, oldest first."""
    if not DEVICE_INSTALL_ENABLED:
        raise DeviceInstallDisabledException()
    _require_device(request, device_id)

    return await device_install_handler.list_for_device(device_id)


@protected_route(
    router.post,
    "/{device_id}/installs/claim",
    [Scope.DEVICES_WRITE, Scope.ROMS_READ],
    responses={
        status.HTTP_403_FORBIDDEN: {},
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_409_CONFLICT: {},
    },
)
async def claim_install_requests(
    request: Request,
    device_id: Annotated[str, PathVar(description="Target device id.")],
) -> list[InstallRequestSchema]:
    """Take every pending request and return all the device holds taken, oldest first."""
    if not DEVICE_INSTALL_ENABLED:
        raise DeviceInstallDisabledException()
    _require_device(request, device_id, device_only=True)

    with _install_errors():
        claim = await device_install_handler.claim(device_id)

    await asyncio.gather(*(emit_install_updated(i) for i in claim.newly_taken))
    return claim.taken


@protected_route(
    router.put,
    "/{device_id}/installs/{request_id}",
    [Scope.DEVICES_WRITE],
    responses={
        status.HTTP_403_FORBIDDEN: {},
        status.HTTP_404_NOT_FOUND: {},
        status.HTTP_409_CONFLICT: {},
    },
)
async def update_install_request(
    request: Request,
    device_id: Annotated[str, PathVar(description="Target device id.")],
    request_id: Annotated[str, PathVar(description="Install request id.")],
    payload: InstallRequestUpdatePayload,
) -> InstallRequestSchema:
    """The device reports the outcome of a request it has taken, which ends the request."""
    if not DEVICE_INSTALL_ENABLED:
        raise DeviceInstallDisabledException()
    device = _require_device(request, device_id, device_only=True)
    await _require_request(request, device_id, request_id)

    with _install_errors():
        ended = await device_install_handler.report(
            request_id, payload.status, payload.reason
        )

    await emit_install_updated(ended)
    await _notify_outcome(ended, device)
    return ended


@protected_route(
    router.delete,
    "/{device_id}/installs/{request_id}",
    [Scope.DEVICES_WRITE],
    responses={status.HTTP_404_NOT_FOUND: {}, status.HTTP_409_CONFLICT: {}},
)
async def cancel_install_request(
    request: Request,
    device_id: Annotated[str, PathVar(description="Target device id.")],
    request_id: Annotated[str, PathVar(description="Install request id.")],
) -> InstallRequestSchema:
    """Cancel a request still pending or taken; one already ended is a 404."""
    if not DEVICE_INSTALL_ENABLED:
        raise DeviceInstallDisabledException()
    _require_device(request, device_id)
    await _require_request(request, device_id, request_id)

    with _install_errors():
        ended = await device_install_handler.cancel(request_id)

    await asyncio.gather(emit_install_cancelled(ended), emit_install_updated(ended))
    return ended
