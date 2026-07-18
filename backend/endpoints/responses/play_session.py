from datetime import datetime
from typing import Literal

from pydantic import ConfigDict

from .base import BaseModel


class PlaySessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    device_id: str | None
    rom_id: int | None
    sync_session_id: int | None
    save_slot: str | None
    start_time: datetime
    end_time: datetime
    duration_ms: int
    created_at: datetime
    updated_at: datetime


class PlaySessionIngestResult(BaseModel):
    index: int
    status: Literal["created", "duplicate", "error"]
    id: int | None = None
    detail: str | None = None


class PlaySessionIngestResponse(BaseModel):
    results: list[PlaySessionIngestResult]
    created_count: int
    skipped_count: int
