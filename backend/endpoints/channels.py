import uuid
from typing import Annotated

from fastapi import HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from decorators.auth import protected_route
from endpoints.responses.snapshots import ChannelSchema, build_channel_schema
from endpoints.snapshots import visible_rom_file
from handler.auth.constants import Scope
from handler.database import db_snapshot_handler
from handler.snapshots import retention
from handler.snapshots.file_key import FileKey
from models.channel import CHANNEL_LABEL_MAX_LENGTH, Channel
from models.user import User
from utils.router import APIRouter

router = APIRouter(prefix="/channels", tags=["channels"])

Label = Annotated[str, Field(min_length=1, max_length=CHANNEL_LABEL_MAX_LENGTH)]


class ChannelCreatePayload(BaseModel):
    rom_file_id: int
    label: Label
    # A client may mint the id itself, so a channel it made offline keeps it.
    id: uuid.UUID | None = None


class ChannelUpdatePayload(BaseModel):
    label: Label | None = None
    is_public: bool | None = None


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found"
    )


def _owned_or_404(id: uuid.UUID, user: User) -> Channel:
    channel = db_snapshot_handler.get_channel(id)
    if channel is None or channel.user_id != user.id:
        raise _not_found()
    return channel


def _sync_visibility(channel_id: uuid.UUID) -> None:
    save_ids, state_ids = db_snapshot_handler.get_content_ids(channel_id)
    db_snapshot_handler.sync_content_visibility(save_ids, state_ids)


@protected_route(router.get, "", [Scope.ASSETS_READ])
def get_channels(
    request: Request,
    rom_file_id: Annotated[list[int] | None, Query()] = None,
    channel_id: Annotated[list[uuid.UUID] | None, Query()] = None,
) -> list[ChannelSchema]:
    """Your channels on the named files, empty ones included, plus any public
    channels you name by id. Each carries its current snapshot, or null."""
    viewer = request.user
    channels: dict[uuid.UUID, Channel] = {}
    for file_id in rom_file_id or []:
        rom_file, rom = visible_rom_file(request, file_id)
        for channel in db_snapshot_handler.get_channels_for_file(
            viewer.id, rom.platform_id, FileKey.of_file(rom_file)
        ):
            channels[channel.id] = channel
    for id in channel_id or []:
        extra = db_snapshot_handler.get_channel(id)
        if extra is None or (extra.user_id != viewer.id and not extra.is_public):
            raise _not_found()
        channels[extra.id] = extra
    return [build_channel_schema(channel, viewer) for channel in channels.values()]


@protected_route(
    router.post, "", [Scope.ASSETS_WRITE], status_code=status.HTTP_201_CREATED
)
def create_channel(request: Request, payload: ChannelCreatePayload) -> ChannelSchema:
    """Create an empty channel on a ROM file. A device's first push into an
    unknown channel id creates it too; creating it first is recommended."""
    viewer = request.user
    rom_file, rom = visible_rom_file(request, payload.rom_file_id)
    if payload.id is not None and db_snapshot_handler.get_channel(payload.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That channel id is taken"
        )
    channel = Channel(
        user_id=viewer.id,
        rom_id=rom.id,
        platform_id=rom.platform_id,
        label=payload.label,
        **FileKey.of_file(rom_file).channel_columns(),
    )
    if payload.id is not None:
        channel.id = payload.id
    return build_channel_schema(db_snapshot_handler.add_channel(channel), viewer)


@protected_route(router.patch, "/{id}", [Scope.ASSETS_WRITE])
def update_channel(
    request: Request, id: uuid.UUID, payload: ChannelUpdatePayload
) -> ChannelSchema:
    """Rename a channel or open it to every user. Owner only."""
    channel = _owned_or_404(id, request.user)
    changes = payload.model_dump(exclude_none=True)
    if changes:
        channel = db_snapshot_handler.update_channel(channel.id, changes)
    if "is_public" in changes:
        _sync_visibility(channel.id)
    return build_channel_schema(channel, request.user)


@protected_route(
    router.delete, "/{id}", [Scope.ASSETS_WRITE], status_code=status.HTTP_204_NO_CONTENT
)
async def delete_channel(request: Request, id: uuid.UUID) -> None:
    """Delete a channel. Its current and pinned snapshots stay as archival backups."""
    channel = _owned_or_404(id, request.user)
    save_ids, state_ids = db_snapshot_handler.get_content_ids(channel.id)
    released = db_snapshot_handler.delete_channel(channel.id)
    await retention.discard_content(released)
    db_snapshot_handler.sync_content_visibility(
        save_ids - {save.id for save in released.saves},
        state_ids - {state.id for state in released.states},
    )
