import uuid
from typing import Any

from models.assets import SaveFormat, SaveShape
from models.channel import Channel
from models.device import Device
from models.snapshot import Snapshot, SnapshotKind
from models.user import User

from .base import BaseModel, UTCDatetime

DIGEST_PREFIX = "sha256:"
# The bank slot whose screenshot stands in for a snapshot whose save has none.
THUMBNAIL_FALLBACK_SLOT = "auto"


class DeviceRefSchema(BaseModel):
    """A device as one viewer sees it: another user's device is never identified."""

    id: str | None
    name: str | None
    client: str | None
    is_own: bool


class ChannelRefSchema(BaseModel):
    id: uuid.UUID
    label: str
    is_public: bool
    is_hardcore: bool
    is_own: bool
    owner_username: str
    current_snapshot_id: int | None
    rom_id: int | None
    # The ROM file the channel is keyed to today, when the library still has it.
    rom_file_id: int | None
    created_at: UTCDatetime
    updated_at: UTCDatetime


class ScreenshotRefSchema(BaseModel):
    id: int
    download_path: str


class SnapshotSaveSchema(BaseModel):
    id: int
    file_name: str
    file_size_bytes: int
    content_hash: str | None
    identity_hash: str | None
    shape: SaveShape | None
    format: SaveFormat | None
    emulator: str | None
    emulator_version: str | None
    core: str | None
    core_version: str | None
    download_path: str
    screenshot: ScreenshotRefSchema | None


class SnapshotStateSchema(BaseModel):
    id: int
    file_name: str
    file_size_bytes: int
    content_hash: str | None
    emulator_version: str | None
    core_version: str | None
    download_path: str
    screenshot: ScreenshotRefSchema | None


class HeldBySchema(BaseModel):
    device: DeviceRefSchema
    synced_at: UTCDatetime


class SnapshotSchema(BaseModel):
    id: int
    digest: str
    kind: SnapshotKind
    parent_snapshot_id: int | None
    channel: ChannelRefSchema | None
    author_user_id: int | None
    device: DeviceRefSchema | None
    emulator: str | None
    rom_id: int | None
    rom_sha1: str | None
    save_target: str | None
    is_hardcore: bool
    is_pinned: bool
    is_public: bool
    created_at: UTCDatetime
    held_by: list[HeldBySchema]
    save: SnapshotSaveSchema | None
    states: dict[str, dict[str, SnapshotStateSchema]]
    # The save's screenshot, else the `auto` state's, else none.
    thumbnail: ScreenshotRefSchema | None


class ChannelSchema(ChannelRefSchema):
    """A channel with its current snapshot, null while the channel is empty."""

    current: SnapshotSchema | None
    snapshot_count: int


class MissingContentSchema(BaseModel):
    missing: list[str]


class CurrentRefSchema(BaseModel):
    id: int
    digest: str


class SnapshotConflictSchema(BaseModel):
    current: CurrentRefSchema | None
    branch: SnapshotSchema


def device_ref(device: Device | None, viewer: User) -> DeviceRefSchema | None:
    if device is None:
        return None
    if device.user_id != viewer.id:
        return DeviceRefSchema(id=None, name=None, client=None, is_own=False)
    return DeviceRefSchema(
        id=device.id, name=device.name, client=device.client, is_own=True
    )


def channel_ref(channel: Channel, viewer: User) -> ChannelRefSchema:
    from handler.database import db_snapshot_handler, db_user_handler

    rom_file = db_snapshot_handler.get_channel_file(channel)
    owner = (
        viewer
        if channel.user_id == viewer.id
        else db_user_handler.get_user(channel.user_id)
    )
    return ChannelRefSchema(
        id=channel.id,
        label=channel.label,
        is_public=channel.is_public,
        is_hardcore=channel.is_hardcore,
        is_own=channel.user_id == viewer.id,
        owner_username=owner.username if owner else "",
        current_snapshot_id=channel.current_snapshot_id,
        rom_id=channel.rom_id,
        rom_file_id=rom_file.id if rom_file else None,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


def can_read(snapshot: Snapshot, channel: Channel | None, viewer: User) -> bool:
    if snapshot.user_id == viewer.id:
        return True
    if channel is not None:
        return channel.is_public
    return snapshot.kind == SnapshotKind.ARCHIVAL and snapshot.is_public


def build_snapshot_schema(
    snapshot: Snapshot, channel: Channel | None, viewer: User
) -> SnapshotSchema:
    from handler.database import db_device_handler, db_snapshot_handler

    content = db_snapshot_handler.get_stored_content(snapshot)
    state_rows = [
        state for slots in content.states.values() for state in slots.values()
    ]
    save_shots, state_shots = db_snapshot_handler.get_thumbnails(
        [content.save.id] if content.save else [], [state.id for state in state_rows]
    )

    def shot(screenshot: Any) -> ScreenshotRefSchema | None:
        if screenshot is None:
            return None
        return ScreenshotRefSchema(
            id=screenshot.id, download_path=screenshot.download_path
        )

    save = content.save
    save_shot = shot(save_shots.get(save.id)) if save else None
    auto_shots = [
        shot(state_shots.get(slots[THUMBNAIL_FALLBACK_SLOT].id))
        for _, slots in sorted(content.states.items())
        if THUMBNAIL_FALLBACK_SLOT in slots
    ]
    thumbnail = save_shot or next((s for s in auto_shots if s), None)
    origin = (
        db_device_handler.get_device_by_id(snapshot.origin_device_id)
        if snapshot.origin_device_id
        else None
    )
    return SnapshotSchema(
        id=snapshot.id,
        digest=f"{DIGEST_PREFIX}{snapshot.digest}",
        kind=snapshot.kind,
        parent_snapshot_id=snapshot.parent_snapshot_id,
        channel=channel_ref(channel, viewer) if channel else None,
        author_user_id=snapshot.author_user_id,
        device=device_ref(origin, viewer),
        emulator=snapshot.emulator,
        rom_id=snapshot.rom_id,
        rom_sha1=snapshot.rom_sha1,
        save_target=snapshot.save_target,
        is_hardcore=snapshot.is_hardcore,
        is_pinned=snapshot.is_pinned,
        is_public=snapshot.is_public,
        created_at=snapshot.created_at,
        held_by=[
            HeldBySchema(
                device=DeviceRefSchema(
                    id=device.id, name=device.name, client=device.client, is_own=True
                ),
                synced_at=sync.synced_at,
            )
            for sync, device in db_snapshot_handler.get_holders(snapshot.id, viewer.id)
        ],
        save=(
            SnapshotSaveSchema(
                id=save.id,
                file_name=save.file_name,
                file_size_bytes=save.file_size_bytes,
                content_hash=save.content_hash,
                identity_hash=save.identity_hash,
                shape=save.shape,
                format=save.format,
                emulator=save.emulator,
                emulator_version=save.emulator_version,
                core=save.core,
                core_version=save.core_version,
                download_path=save.download_path,
                screenshot=save_shot,
            )
            if save
            else None
        ),
        states={
            core: {
                slot: SnapshotStateSchema(
                    id=state.id,
                    file_name=state.file_name,
                    file_size_bytes=state.file_size_bytes,
                    content_hash=state.content_hash,
                    emulator_version=state.emulator_version,
                    core_version=state.core_version,
                    download_path=state.download_path,
                    screenshot=shot(state_shots.get(state.id)),
                )
                for slot, state in slots.items()
            }
            for core, slots in content.states.items()
        },
        thumbnail=thumbnail,
    )


def build_channel_schema(channel: Channel, viewer: User) -> ChannelSchema:
    from handler.database import db_snapshot_handler

    current = (
        db_snapshot_handler.get_snapshot(channel.current_snapshot_id)
        if channel.current_snapshot_id
        else None
    )
    return ChannelSchema(
        **channel_ref(channel, viewer).model_dump(),
        current=build_snapshot_schema(current, channel, viewer) if current else None,
        snapshot_count=db_snapshot_handler.count_snapshots(channel.id),
    )
