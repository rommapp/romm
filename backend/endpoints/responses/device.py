from pydantic import ConfigDict

from models.device import SyncMode

from .base import BaseModel, UTCDatetime


class DeviceSyncSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: str
    device_name: str | None
    last_synced_at: UTCDatetime
    is_untracked: bool
    is_current: bool


class DeviceSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    name: str | None
    platform: str | None
    client: str | None
    client_version: str | None
    ip_address: str | None
    mac_address: str | None
    hostname: str | None
    sync_mode: SyncMode
    sync_enabled: bool
    sync_config: dict | None
    last_seen: UTCDatetime | None
    created_at: UTCDatetime
    updated_at: UTCDatetime


class DeviceCreateResponse(BaseModel):
    device_id: str
    name: str | None
    created_at: UTCDatetime
