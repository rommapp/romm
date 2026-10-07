import uuid
from collections.abc import Collection, Sequence
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


def channel_refs(
    channels: Collection[Channel], viewer: User
) -> dict[uuid.UUID, ChannelRefSchema]:
    """Each channel's ref by channel id, in a fixed number of queries."""
    from handler.database import db_snapshot_handler, db_user_handler

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
    return {
        channel.id: ChannelRefSchema(
            id=channel.id,
            label=channel.label,
            is_public=channel.is_public,
            is_hardcore=channel.is_hardcore,
            is_own=channel.user_id == viewer.id,
            owner_username=usernames.get(channel.user_id, ""),
            current_snapshot_id=channel.current_snapshot_id,
            rom_id=channel.rom_id,
            rom_file_id=(rom_files[channel.id].id if channel.id in rom_files else None),
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )
        for channel in channels
    }


def _shot(screenshot: Any) -> ScreenshotRefSchema | None:
    if screenshot is None:
        return None
    return ScreenshotRefSchema(id=screenshot.id, download_path=screenshot.download_path)


def build_snapshot_schema(
    snapshot: Snapshot, channel: Channel | None, viewer: User
) -> SnapshotSchema:
    return build_snapshot_schemas([(snapshot, channel)], viewer)[0]


def build_snapshot_schemas(
    snapshots: Sequence[tuple[Snapshot, Channel | None]],
    viewer: User,
    refs: dict[uuid.UUID, ChannelRefSchema] | None = None,
) -> list[SnapshotSchema]:
    """Each snapshot's schema, with its channel, in a fixed number of queries
    however many snapshots there are.

    Args:
        refs: channel refs the caller already built, by channel id.
    """
    from handler.database import db_snapshot_handler

    refs = dict(refs or {})

    contents = db_snapshot_handler.get_stored_contents([s for s, _ in snapshots])
    save_shots, state_shots = db_snapshot_handler.get_thumbnails(
        [c.save.id for c in contents.values() if c.save],
        [state.id for c in contents.values() for state in c.state_rows],
    )
    devices = db_snapshot_handler.get_devices(
        {s.origin_device_id for s, _ in snapshots if s.origin_device_id}
    )
    holders = db_snapshot_handler.get_holders_by_snapshot(
        [s.id for s, _ in snapshots], viewer.id
    )
    pin_counts, my_pins = db_snapshot_handler.get_pins(
        [s.id for s, _ in snapshots], viewer.id
    )
    unbuilt = {c.id: c for _, c in snapshots if c is not None and c.id not in refs}
    refs.update(channel_refs(unbuilt.values(), viewer))
    return [
        _snapshot_schema(
            snapshot,
            refs[channel.id] if channel else None,
            contents[snapshot.id],
            save_shots,
            state_shots,
            devices.get(snapshot.origin_device_id or ""),
            holders.get(snapshot.id, []),
            (snapshot.id in my_pins, pin_counts.get(snapshot.id, 0)),
            viewer,
        )
        for snapshot, channel in snapshots
    ]


def _snapshot_schema(
    snapshot: Snapshot,
    channel: ChannelRefSchema | None,
    content: Any,
    save_shots: dict[int, Any],
    state_shots: dict[int, Any],
    origin: Device | None,
    holders: Sequence[tuple[Any, Device]],
    pins: tuple[bool, int],
    viewer: User,
) -> SnapshotSchema:
    save = content.save
    save_shot = _shot(save_shots.get(save.id)) if save else None
    auto_shots = [
        _shot(state_shots.get(slots[THUMBNAIL_FALLBACK_SLOT].id))
        for _, slots in sorted(content.states.items())
        if THUMBNAIL_FALLBACK_SLOT in slots
    ]
    thumbnail = save_shot or next((s for s in auto_shots if s), None)
    return SnapshotSchema(
        id=snapshot.id,
        digest=f"{DIGEST_PREFIX}{snapshot.digest}",
        kind=snapshot.kind,
        parent_snapshot_id=snapshot.parent_snapshot_id,
        channel=channel,
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
                    screenshot=_shot(state_shots.get(state.id)),
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
    from handler.database import db_snapshot_handler

    currents = db_snapshot_handler.get_snapshots(
        {c.current_snapshot_id for c in channels if c.current_snapshot_id}
    )
    counts = db_snapshot_handler.count_snapshots_by_channel([c.id for c in channels])
    refs = channel_refs(channels, viewer)
    with_current = [
        (currents[c.current_snapshot_id], c)
        for c in channels
        if c.current_snapshot_id in currents
    ]
    schemas = {
        snapshot.id: schema
        for (snapshot, _), schema in zip(
            with_current,
            build_snapshot_schemas(with_current, viewer, refs),
            strict=True,
        )
    }
    return [
        ChannelSchema(
            **refs[c.id].model_dump(),
            current=(
                schemas.get(c.current_snapshot_id) if c.current_snapshot_id else None
            ),
            snapshot_count=counts.get(c.id, 0),
        )
        for c in channels
    ]
