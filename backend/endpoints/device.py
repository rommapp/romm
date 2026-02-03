import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Body, HTTPException, Request, Response, status

from decorators.auth import protected_route
from endpoints.responses.device import DeviceCreateResponse, DeviceSchema
from handler.auth.constants import Scope
from handler.database import db_device_handler, db_device_save_sync_handler
from logger.logger import log
from models.device import Device
from utils.router import APIRouter

router = APIRouter(
    prefix="/devices",
    tags=["devices"],
)


@protected_route(router.post, "", [Scope.DEVICES_WRITE])
def register_device(
    request: Request,
    response: Response,
    name: str | None = Body(None, embed=True),
    platform: str | None = Body(None, embed=True),
    client: str | None = Body(None, embed=True),
    client_version: str | None = Body(None, embed=True),
    ip_address: str | None = Body(None, embed=True),
    mac_address: str | None = Body(None, embed=True),
    hostname: str | None = Body(None, embed=True),
    allow_existing: bool = Body(False, embed=True),
    allow_duplicate: bool = Body(False, embed=True),
    reset_syncs: bool = Body(False, embed=True),
) -> DeviceCreateResponse:
    existing_device = None
    if not allow_duplicate:
        existing_device = db_device_handler.get_device_by_fingerprint(
            user_id=request.user.id,
            mac_address=mac_address,
            hostname=hostname,
            platform=platform,
        )

    if existing_device:
        if not allow_existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "device_exists",
                    "message": "A device with this fingerprint already exists",
                    "device_id": existing_device.id,
                },
            )

        if reset_syncs:
            db_device_save_sync_handler.delete_syncs_for_device(
                device_id=existing_device.id
            )

        db_device_handler.update_last_seen(
            device_id=existing_device.id, user_id=request.user.id
        )
        log.info(
            f"Returned existing device {existing_device.id} for user {request.user.username}"
        )

        response.status_code = status.HTTP_200_OK
        return DeviceCreateResponse(
            device_id=existing_device.id,
            name=existing_device.name,
            created_at=existing_device.created_at,
        )

    response.status_code = status.HTTP_201_CREATED
    device_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    device = Device(
        id=device_id,
        user_id=request.user.id,
        name=name,
        platform=platform,
        client=client,
        client_version=client_version,
        ip_address=ip_address,
        mac_address=mac_address,
        hostname=hostname,
        last_seen=now,
    )

    db_device = db_device_handler.add_device(device)
    log.info(f"Registered device {device_id} for user {request.user.username}")

    return DeviceCreateResponse(
        device_id=db_device.id,
        name=db_device.name,
        created_at=db_device.created_at,
    )


@protected_route(router.get, "", [Scope.DEVICES_READ])
def get_devices(request: Request) -> list[DeviceSchema]:
    devices = db_device_handler.get_devices(user_id=request.user.id)
    return [DeviceSchema.model_validate(device) for device in devices]


@protected_route(router.get, "/{device_id}", [Scope.DEVICES_READ])
def get_device(request: Request, device_id: str) -> DeviceSchema:
    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    return DeviceSchema.model_validate(device)


@protected_route(router.put, "/{device_id}", [Scope.DEVICES_WRITE])
def update_device(
    request: Request,
    device_id: str,
    name: str | None = Body(None, embed=True),
    platform: str | None = Body(None, embed=True),
    client: str | None = Body(None, embed=True),
    client_version: str | None = Body(None, embed=True),
    ip_address: str | None = Body(None, embed=True),
    mac_address: str | None = Body(None, embed=True),
    hostname: str | None = Body(None, embed=True),
    sync_enabled: bool | None = Body(None, embed=True),
) -> DeviceSchema:
    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )

    update_data: dict[str, Any] = {}
    if name is not None:
        update_data["name"] = name
    if platform is not None:
        update_data["platform"] = platform
    if client is not None:
        update_data["client"] = client
    if client_version is not None:
        update_data["client_version"] = client_version
    if ip_address is not None:
        update_data["ip_address"] = ip_address
    if mac_address is not None:
        update_data["mac_address"] = mac_address
    if hostname is not None:
        update_data["hostname"] = hostname
    if sync_enabled is not None:
        update_data["sync_enabled"] = sync_enabled

    if update_data:
        device = db_device_handler.update_device(
            device_id=device_id,
            user_id=request.user.id,
            data=update_data,
        )

    return DeviceSchema.model_validate(device)


@protected_route(
    router.delete,
    "/{device_id}",
    [Scope.DEVICES_WRITE],
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_device(request: Request, device_id: str) -> None:
    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )

    db_device_handler.delete_device(device_id=device_id, user_id=request.user.id)
    log.info(f"Deleted device {device_id} for user {request.user.username}")
