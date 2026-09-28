import enum
from typing import Annotated

from pydantic import Field

from ..base import BaseModel, UTCDatetime


class InstallStatus(enum.StrEnum):
    PENDING = "pending"
    TAKEN = "taken"
    DONE = "done"
    ALREADY_INSTALLED = "already_installed"
    FAILED = "failed"
    CANCELLED = "cancelled"


InstallReason = Annotated[str, Field(max_length=500)]


class InstallRequestSchema(BaseModel):
    """An install request, as served and as stored in Redis while pending or taken."""

    id: str
    user_id: int
    device_id: str
    rom_id: int
    file_ids: list[int]
    status: InstallStatus
    reason: InstallReason | None
    created_at: UTCDatetime
    updated_at: UTCDatetime
