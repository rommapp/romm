from models.smb import SmbAccessMode
from pydantic import BaseModel, ConfigDict

from .base import UTCDatetime


class SmbPlatformPermissionSchema(BaseModel):
    platform_id: int
    platform_name: str
    platform_fs_slug: str
    share_name: str
    access: SmbAccessMode


class SmbUserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    permissions: list[SmbPlatformPermissionSchema]
    created_at: UTCDatetime
    updated_at: UTCDatetime


class SmbUserSecretSchema(SmbUserSchema):
    password: str


class SmbStatusSchema(BaseModel):
    enabled: bool
    controller_online: bool
    samba_running: bool
    samba_version: str | None = None
    advertised_host: str | None = None
    advertised_port: int
    workgroup: str
    started_at: UTCDatetime | None = None
    user_count: int


class SmbLogsSchema(BaseModel):
    lines: list[str]
