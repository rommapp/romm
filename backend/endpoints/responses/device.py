from datetime import datetime

from models.device import SyncMode

from .base import BaseModel


class DeviceSyncSchema(BaseModel):
    device_id: str
    device_name: str | None
    last_synced_at: datetime
    is_untracked: bool
    is_current: bool

    class Config:
        from_attributes = True


class DeviceSchema(BaseModel):
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
    last_seen: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceCreateResponse(BaseModel):
    device_id: str
    name: str | None
    created_at: datetime
