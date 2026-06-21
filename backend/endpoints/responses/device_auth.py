from pydantic import Field

from .base import BaseModel, UTCDatetime


class DeviceAuthInitPayload(BaseModel):
    client_device_identifier: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    client: str = Field(min_length=1, max_length=50)
    platform: str | None = Field(default=None, max_length=50)
    client_version: str | None = Field(default=None, max_length=50)
    requested_scopes: list[str] = Field(min_length=1)


class DeviceAuthInitResponse(BaseModel):
    device_code: str
    user_code: str
    verification_path: str = Field(
        description=(
            "Relative web-UI path (/pair/device). The client joins it with the "
            "origin it was configured to reach; the server is origin-agnostic."
        )
    )
    verification_path_complete: str = Field(
        description="Same path with ?user_code= appended, for QR display."
    )
    expires_in: int
    interval: int


class DeviceAuthPendingSchema(BaseModel):
    client_device_identifier: str
    name: str
    client: str
    platform: str | None
    client_version: str | None
    requested_scopes: list[str]
    allowed_scopes: list[str]
    expires_at: UTCDatetime


class DeviceAuthApprovePayload(BaseModel):
    user_code: str = Field(min_length=1, max_length=32)
    approved_scopes: list[str] = Field(min_length=1)
    device_name: str | None = Field(default=None, max_length=255)
    expires_in: str | None = None


class DeviceAuthApproveResponse(BaseModel):
    device_id: str
    device_name: str | None


class DeviceAuthDenyPayload(BaseModel):
    user_code: str = Field(min_length=1, max_length=32)


class DeviceAuthTokenPayload(BaseModel):
    device_code: str = Field(min_length=1, max_length=128)


class DeviceAuthTokenResponse(BaseModel):
    access_token: str
    device_id: str
    scopes: list[str]
    expires_at: UTCDatetime | None
