from typing import Literal

from pydantic import ConfigDict

from .base import BaseModel, UTCDatetime


class SyncOperationSchema(BaseModel):
    action: Literal["upload", "download", "conflict", "no_op"]
    rom_id: int
    save_id: int | None = None
    file_name: str
    slot: str | None = None
    emulator: str | None = None
    reason: str
    server_updated_at: UTCDatetime | None = None
    server_content_hash: str | None = None


class SyncNegotiateResponse(BaseModel):
    session_id: int
    operations: list[SyncOperationSchema]
    total_upload: int
    total_download: int
    total_conflict: int
    total_no_op: int


class SyncSessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    user_id: int
    status: str
    initiated_at: UTCDatetime
    completed_at: UTCDatetime | None = None
    operations_planned: int
    operations_completed: int
    operations_failed: int
    error_message: str | None = None
    created_at: UTCDatetime
    updated_at: UTCDatetime
