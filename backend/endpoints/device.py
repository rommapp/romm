import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, Request, Response, status
from pydantic import BaseModel, model_validator

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


class DeviceCreatePayload(BaseModel):
    name: str | None = None
    platform: str | None = None
    client: str | None = None
    client_version: str | None = None
    ip_address: str | None = None
    mac_address: str | None = None
    hostname: str | None = None
    allow_existing: bool = True
    allow_duplicate: bool = False
    reset_syncs: bool = False

    @model_validator(mode="after")
    def _duplicate_disables_existing(self) -> "DeviceCreatePayload":
        if self.allow_duplicate:
            self.allow_existing = False
        return self


class DeviceUpdatePayload(BaseModel):
    name: str | None = None
    platform: str | None = None
    client: str | None = None
    client_version: str | None = None
    ip_address: str | None = None
    mac_address: str | None = None
    hostname: str | None = None
    sync_enabled: bool | None = None


@protected_route(router.post, "", [Scope.DEVICES_WRITE])
def register_device(
    request: Request,
    response: Response,
    payload: DeviceCreatePayload,
) -> DeviceCreateResponse:
    existing_device = None
    if not payload.allow_duplicate:
        existing_device = db_device_handler.get_device_by_fingerprint(
            user_id=request.user.id,
            mac_address=payload.mac_address,
            hostname=payload.hostname,
            platform=payload.platform,
        )

    if existing_device:
        if not payload.allow_existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "device_exists",
                    "message": "A device with this fingerprint already exists",
                    "device_id": existing_device.id,
                },
            )

        if payload.reset_syncs:
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
        name=payload.name,
        platform=payload.platform,
        client=payload.client,
        client_version=payload.client_version,
        ip_address=payload.ip_address,
        mac_address=payload.mac_address,
        hostname=payload.hostname,
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
    payload: DeviceUpdatePayload,
) -> DeviceSchema:
    device = db_device_handler.get_device(device_id=device_id, user_id=request.user.id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
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
