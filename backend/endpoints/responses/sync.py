from typing import Literal

from pydantic import ConfigDict, Field

from .base import BaseModel, UTCDatetime
from .play_session import PlaySessionIngestResponse


class SyncOperationSchema(BaseModel):
    action: Literal["upload", "download", "conflict", "no_op"] = Field(
        description=(
            "Operation the client should perform. 'upload' when the client has a "
            "save the server lacks (including any null-slot save, which is never "
            "paired with server saves), 'download' when the server has a newer or "
            "unknown save, 'conflict' when both sides changed independently, and "
            "'no_op' when no action is needed."
        )
    )
    rom_id: int = Field(description="ID of the ROM this operation applies to.")
    save_id: int | None = Field(
        default=None,
        description="ID of the server save, if one exists (null for uploads).",
    )
    file_name: str = Field(description="Name of the save file.")
    slot: str | None = Field(
        default=None,
        description=(
            "Slot the operation applies to. Echoes the client slot for uploads; "
            "for downloads and conflicts it is the server save's slot."
        ),
    )
    emulator: str | None = Field(
        default=None, description="Emulator associated with the save, if known."
    )
    reason: str = Field(
        description="Human-readable explanation of why this operation was chosen."
    )
    server_updated_at: UTCDatetime | None = Field(
        default=None,
        description="Last-modified timestamp of the server save, when applicable.",
    )
    server_content_hash: str | None = Field(
        default=None,
        description="Content hash of the server save, when applicable.",
    )


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


class SyncCompleteResponse(BaseModel):
    session: SyncSessionSchema
    play_session_ingest: PlaySessionIngestResponse | None = None
