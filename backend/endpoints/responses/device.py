from typing import Any

from pydantic import ConfigDict, field_serializer

from models.device import SyncMode

from .base import BaseModel, UTCDatetime

SENSITIVE_SYNC_CONFIG_KEYS = {"ssh_password", "ssh_key_path"}


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

    @field_serializer("sync_config")
    @classmethod
    def mask_sensitive_fields(cls, v: dict | None) -> dict[str, Any] | None:
        if not v:
            return v
        return {
            k: "********" if k in SENSITIVE_SYNC_CONFIG_KEYS else val
            for k, val in v.items()
        }


class DeviceCreateResponse(BaseModel):
    device_id: str
    name: str | None
    created_at: UTCDatetime
