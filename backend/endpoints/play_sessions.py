from datetime import datetime

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator

from decorators.auth import protected_route
from endpoints.responses.play_session import (
    PlaySessionIngestResponse,
    PlaySessionIngestResult,
    PlaySessionSchema,
)
from handler.auth.constants import Scope
from handler.database import db_play_session_handler
from handler.play_session_handler import ingest_play_sessions as _ingest
from logger.logger import log
from utils.router import APIRouter

router = APIRouter(
    prefix="/play-sessions",
    tags=["play-sessions"],
)

MAX_BATCH_SIZE = 100


class PlaySessionEntry(BaseModel):
    rom_id: int | None = None
    save_slot: str | None = None
    start_time: datetime
    end_time: datetime
    duration_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_times(self) -> "PlaySessionEntry":
        self.start_time = self.start_time.replace(microsecond=0)
        self.end_time = self.end_time.replace(microsecond=0)
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class PlaySessionIngestPayload(BaseModel):
    device_id: str | None = None
    sessions: list[PlaySessionEntry]


@protected_route(
    router.post, "", [Scope.ROMS_USER_WRITE], status_code=status.HTTP_201_CREATED
)
def ingest_play_sessions(
    request: Request,
    payload: PlaySessionIngestPayload,
) -> PlaySessionIngestResponse:
    if not payload.sessions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must contain at least one session",
        )
    if len(payload.sessions) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size exceeds maximum of {MAX_BATCH_SIZE}",
        )

    device_id = payload.device_id or getattr(request.state, "device_id", None)

    summary = _ingest(
        user_id=request.user.id,
        username=request.user.username,
        entries=[
            {
                "rom_id": s.rom_id,
                "save_slot": s.save_slot,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "duration_ms": s.duration_ms,
            }
            for s in payload.sessions
        ],
        device_id=device_id,
    )

    return PlaySessionIngestResponse(
        results=[
            PlaySessionIngestResult(
                index=r.get("index"),
                status=r.get("status"),
                id=r.get("id"),
                detail=r.get("detail"),
            )
            for r in summary["results"]
        ],
        created_count=summary["created_count"],
        skipped_count=summary["skipped_count"],
    )


@protected_route(router.get, "", [Scope.ROMS_USER_READ])
def get_play_sessions(
    request: Request,
    rom_id: int | None = None,
    device_id: str | None = None,
    start_after: datetime | None = None,
    end_before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[PlaySessionSchema]:
    effective_device_id = device_id or getattr(request.state, "device_id", None)
    sessions = db_play_session_handler.get_sessions(
        user_id=request.user.id,
        rom_id=rom_id,
        device_id=effective_device_id,
        start_after=start_after,
        end_before=end_before,
        limit=limit if start_after is None and end_before is None else None,
        offset=offset,
    )
    return [PlaySessionSchema.model_validate(s) for s in sessions]


@protected_route(
    router.delete,
    "/{session_id}",
    [Scope.ROMS_USER_WRITE],
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_play_session(request: Request, session_id: int) -> None:
    deleted = db_play_session_handler.delete_session(
        session_id=session_id, user_id=request.user.id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Play session {session_id} not found",
        )
    log.info(f"Deleted play session {session_id} for user {request.user.username}")
