import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import Field

from models.assets import SaveFormat, SaveShape, Screenshot
from models.channel import Channel
from models.device import Device
from models.device_channel_sync import DeviceChannelSync
from models.snapshot import ConflictReason, Snapshot, SnapshotKind
from models.user import User

from .base import BaseModel, UTCDatetime

if TYPE_CHECKING:
    from handler.database.snapshots_handler import StoredContent

DIGEST_PREFIX = "sha256:"
# The bank slot whose screenshot stands in for a snapshot whose save has none.
THUMBNAIL_FALLBACK_SLOT = "auto"


class DeviceRefSchema(BaseModel):
    """A device as one viewer sees it: another user's device is never identified."""

    id: str | None
    name: str | None
    client: str | None
    is_own: bool


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
    channel_id: uuid.UUID | None
    author_user_id: int | None
    device: DeviceRefSchema | None
    emulator: str | None
    rom_id: int | None
    rom_sha1: str | None
    save_target: str | None
    is_hardcore: bool
    # Whether the viewer pinned it; `pin_count` counts every user's pin.
    is_pinned: bool
    pin_count: int
    is_public: bool
    created_at: UTCDatetime
    held_by: list[HeldBySchema]
    save: SnapshotSaveSchema | None
    states: dict[str, dict[str, SnapshotStateSchema]]
    # The save's screenshot, else the `auto` state's, else none.
    thumbnail: ScreenshotRefSchema | None


class ChannelSchema(BaseModel):
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
    # Null while the channel is empty.
    current: SnapshotSchema | None
    snapshot_count: int


class MissingContentSchema(BaseModel):
    missing: list[str]


class SnapshotConflictSchema(BaseModel):
    current: SnapshotSchema | None
    branch: SnapshotSchema
    reason: ConflictReason = Field(
        description=(
            "`moved`: the channel moved on from the current the push built on. "
            "`moved_from_older`: the push built on a snapshot older than the "
            "current it expected, and the channel moved on from that current too."
        )
    )


def device_ref(device: Device | None, viewer: User) -> DeviceRefSchema | None:
    if device is None:
        return None
    if device.user_id != viewer.id:
        return DeviceRefSchema(id=None, name=None, client=None, is_own=False)
    return DeviceRefSchema(
        id=device.id, name=device.name, client=device.client, is_own=True
    )


def _screenshot_ref(screenshot: Screenshot | None) -> ScreenshotRefSchema | None:
    if screenshot is None:
        return None
    return ScreenshotRefSchema(id=screenshot.id, download_path=screenshot.download_path)


def build_snapshot_schema(snapshot: Snapshot, viewer: User) -> SnapshotSchema:
    return build_snapshot_schemas([snapshot], viewer)[0]


def build_snapshot_schemas(
    snapshots: Sequence[Snapshot], viewer: User
) -> list[SnapshotSchema]:
    """Each snapshot's schema, in a fixed number of queries however many
    snapshots there are."""
    from handler.database import db_snapshot_handler

    ids = [s.id for s in snapshots]
    contents = db_snapshot_handler.get_stored_contents(snapshots)
    save_shots, state_shots = db_snapshot_handler.get_thumbnails(
        [c.save.id for c in contents.values() if c.save],
        [state.id for c in contents.values() for state in c.state_rows],
    )
    devices = db_snapshot_handler.get_devices(
        {s.origin_device_id for s in snapshots if s.origin_device_id}
    )
    holders = db_snapshot_handler.get_holders_by_snapshot(ids, viewer.id)
    pin_counts, my_pins = db_snapshot_handler.get_pins(ids, viewer.id)
    return [
        _snapshot_schema(
            snapshot,
            contents[snapshot.id],
            save_shots,
            state_shots,
            devices.get(snapshot.origin_device_id or ""),
            holders.get(snapshot.id, []),
            (snapshot.id in my_pins, pin_counts.get(snapshot.id, 0)),
            viewer,
        )
        for snapshot in snapshots
    ]


def _snapshot_schema(
    snapshot: Snapshot,
    content: "StoredContent",
    save_shots: dict[int, Screenshot],
    state_shots: dict[int, Screenshot],
    origin: Device | None,
    holders: Sequence[tuple[DeviceChannelSync, Device]],
    pins: tuple[bool, int],
    viewer: User,
) -> SnapshotSchema:
    save = content.save
    save_shot = _screenshot_ref(save_shots.get(save.id)) if save else None
    auto_shots = [
        _screenshot_ref(state_shots.get(slots[THUMBNAIL_FALLBACK_SLOT].id))
        for _, slots in sorted(content.states.items())
        if THUMBNAIL_FALLBACK_SLOT in slots
    ]
    thumbnail = save_shot or next((s for s in auto_shots if s), None)
    return SnapshotSchema(
        id=snapshot.id,
        digest=f"{DIGEST_PREFIX}{snapshot.digest}",
        kind=snapshot.kind,
        parent_snapshot_id=snapshot.parent_snapshot_id,
        channel_id=snapshot.channel_id,
        author_user_id=snapshot.author_user_id,
        device=device_ref(origin, viewer),
        emulator=snapshot.emulator,
        rom_id=snapshot.rom_id,
        rom_sha1=snapshot.rom_sha1,
        save_target=snapshot.save_target,
        is_hardcore=snapshot.is_hardcore,
        is_pinned=pins[0],
        pin_count=pins[1],
        is_public=snapshot.is_public,
        created_at=snapshot.created_at,
        held_by=[
            HeldBySchema(
                device=DeviceRefSchema(
                    id=device.id, name=device.name, client=device.client, is_own=True
                ),
                synced_at=sync.synced_at,
            )
            for sync, device in holders
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
                    screenshot=_screenshot_ref(state_shots.get(state.id)),
                )
                for slot, state in slots.items()
            }
            for core, slots in content.states.items()
        },
        thumbnail=thumbnail,
    )


def build_channel_schema(channel: Channel, viewer: User) -> ChannelSchema:
    return build_channel_schemas([channel], viewer)[0]


def build_channel_schemas(
    channels: Sequence[Channel], viewer: User
) -> list[ChannelSchema]:
    """Each channel's schema with its current snapshot, batched like
    `build_snapshot_schemas`."""
    from handler.database import db_snapshot_handler, db_user_handler

    currents = db_snapshot_handler.get_snapshots(
        {c.current_snapshot_id for c in channels if c.current_snapshot_id}
    )
    schemas = {
        schema.id: schema
        for schema in build_snapshot_schemas(list(currents.values()), viewer)
    }
    counts = db_snapshot_handler.count_snapshots_by_channel([c.id for c in channels])
    rom_files = db_snapshot_handler.get_channel_files(channels)
    others = {c.user_id for c in channels if c.user_id != viewer.id}
    usernames = {viewer.id: viewer.username} | {
        user.id: user.username
        for user in (
            db_user_handler.get_users(ids=others, only_fields=[User.id, User.username])
            if others
            else []
        )
    }
    return [
        ChannelSchema(
            id=c.id,
            label=c.label,
            is_public=c.is_public,
            is_hardcore=c.is_hardcore,
            is_own=c.user_id == viewer.id,
            owner_username=usernames.get(c.user_id, ""),
            current_snapshot_id=c.current_snapshot_id,
            rom_id=c.rom_id,
            rom_file_id=rom_files[c.id].id if c.id in rom_files else None,
            created_at=c.created_at,
            updated_at=c.updated_at,
            current=(
                schemas.get(c.current_snapshot_id) if c.current_snapshot_id else None
            ),
            snapshot_count=counts.get(c.id, 0),
        )
        for c in channels
    ]
