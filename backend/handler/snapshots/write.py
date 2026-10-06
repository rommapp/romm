"""`write_snapshot`: the one path that stores a save, a state or a snapshot.

Bytes land on disk first, then one transaction inserts the content rows and the
snapshot and moves the channel's pointer under a row lock. A failed write
removes the files it wrote.
"""

import enum
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from fastapi import UploadFile
from sqlalchemy.orm import Session

from handler.asset_store import AssetContent, remove_asset_file
from handler.database import db_snapshot_handler, db_user_handler
from handler.database.base_handler import sync_session
from handler.database.snapshots_handler import StoredContent
from handler.filesystem import fs_asset_handler
from handler.snapshots import retention
from handler.snapshots.file_key import FileKey
from handler.snapshots.hashing import identity_hash, identity_hash_of_file
from handler.snapshots.manifest import (
    CARRY,
    Carry,
    Manifest,
    Resolved,
    resolve,
)
from models.assets import Save, Screenshot, State
from models.channel import Channel
from models.rom import Rom, RomFile
from models.snapshot import Snapshot, SnapshotKind, SnapshotState
from models.user import User
from utils.uploads import apply_datetime_tag, sanitize_asset_filename

SAVE_PART = "save"


def state_part(core: str, slot: str) -> str:
    """The part name, and missing-content key, of one bank slot."""
    return f"state:{core}:{slot}"


class SnapshotWriteError(Exception):
    """A push the server refuses. Nothing it wrote survives."""


class ContentMissing(SnapshotWriteError):
    def __init__(self, keys: list[str]):
        super().__init__(f"missing content for {', '.join(keys)}")
        self.keys = keys


class ContentMismatch(SnapshotWriteError):
    def __init__(self, key: str):
        super().__init__(f"{key} does not hash to the manifest's value")
        self.key = key


class NotVisible(SnapshotWriteError):
    def __init__(self, what: str):
        super().__init__(f"{what} not found")
        self.what = what


class FileMismatch(SnapshotWriteError):
    """The ROM file is not the one the channel was made with."""


class LabelRequired(SnapshotWriteError):
    """A new channel needs a label."""


class HardcoreDowngrade(SnapshotWriteError):
    """A softcore save would replace a hardcore current without the user's approval."""


class Outcome(enum.StrEnum):
    CREATED = "created"
    UNCHANGED = "unchanged"
    BRANCHED = "branched"


@dataclass(frozen=True)
class UploadPart:
    """One part of a push. A part with no `content` carries only a screenshot
    for content the server already holds."""

    content: AssetContent | None
    file_name: str
    screenshot: AssetContent | None = None
    screenshot_name: str | None = None


@dataclass(frozen=True)
class ChannelTarget:
    expected_current_id: int | None
    id: uuid.UUID | None = None
    label: str | None = None


@dataclass(frozen=True)
class SnapshotWrite:
    author: User
    rom: Rom
    manifest: Manifest
    # None writes an archival snapshot, which moves no pointer.
    channel: ChannelTarget | None
    rom_file: RomFile | None = None
    # Left out, the parent is the current the push expects.
    parent_snapshot_id: int | None | Literal[Carry.PARENT] = CARRY
    # The device recorded as holding the new snapshot.
    device_id: str | None = None
    # The device that wrote the bytes, when not `device_id`: a clone keeps its source's.
    origin_device_id: str | None = None
    parts: Mapping[str, UploadPart] = field(default_factory=dict)
    is_public: bool = False
    # A legacy row, held by no snapshot yet, to hold as the save.
    adopt_save: Save | None = None


@dataclass(frozen=True)
class WriteResult:
    snapshot: Snapshot
    outcome: Outcome
    current: Snapshot | None


@dataclass
class _StoredFile:
    row: Save | State
    screenshot: Screenshot | None = None


@dataclass
class _Plan:
    owner: User
    channel: Channel | None
    parent: Snapshot | None
    resolved: Resolved
    # The current snapshot this push adds no progress to: the same content, or
    # a save whose clock alone moved.
    same_as: int | None = None
    saves: dict[str, Save] = field(default_factory=dict)
    states: dict[str, State] = field(default_factory=dict)
    written_paths: list[str] = field(default_factory=list)
    # Screenshots for rows already stored, kept even when the push changes nothing.
    shot_paths: list[str] = field(default_factory=list)

    @property
    def unchanged(self) -> bool:
        return self.same_as is not None


class _CurrentMoved(Exception):
    """The current a plan matched moved before the commit's lock."""


def _part_bytes(content: AssetContent) -> bytes:
    if isinstance(content, bytes):
        return content
    stream = content.file if isinstance(content, UploadFile) else content
    position = stream.tell()
    data: bytes = stream.read()
    stream.seek(position)
    return data


def _content(write: SnapshotWrite, key: str) -> AssetContent | None:
    """The bytes the push sends for `key`, None when it sends none or only a screenshot."""
    part = write.parts.get(key)
    return part.content if part else None


async def _clock_only(
    write: SnapshotWrite, current: Snapshot, resolved: Resolved
) -> bool:
    """Whether the push differs from `current` only in its save's clock."""
    sent = _content(write, SAVE_PART)
    if resolved.save is None or sent is None:
        return False
    held = db_snapshot_handler.get_stored_content(current)
    if (
        held.save is None
        or not held.save.identity_hash
        or held.resolved().bank != resolved.bank
    ):
        return False
    return await identity_hash(_part_bytes(sent)) == held.save.identity_hash


def _parent_id(write: SnapshotWrite) -> int | None:
    if isinstance(write.parent_snapshot_id, Carry):
        return write.channel.expected_current_id if write.channel else None
    return write.parent_snapshot_id


def _can_read(snapshot: Snapshot, user: User, channel: Channel | None) -> bool:
    if snapshot.user_id == user.id:
        return True
    if channel is not None:
        return channel.is_public
    return snapshot.kind == SnapshotKind.ARCHIVAL and snapshot.is_public


async def _hash_unhashed(content: StoredContent) -> None:
    """Fill content hashes older rows never recorded, so a digest can cover them."""
    rows: list[Save | State] = [content.save] if content.save else []
    rows += [state for slots in content.states.values() for state in slots.values()]
    for row in rows:
        if row.content_hash:
            continue
        row.content_hash = await fs_asset_handler.compute_content_hash(row.full_path)
        with sync_session.begin() as session:
            session.merge(row)


def _target_channel(write: SnapshotWrite) -> Channel | None:
    target = write.channel
    if target is None:
        return None
    if write.rom_file is None:
        raise ValueError("a channel push names its ROM file")

    channel = db_snapshot_handler.get_channel(target.id) if target.id else None
    if channel is None:
        if not target.label:
            raise LabelRequired("a new channel needs a label")
        return None
    if channel.user_id != write.author.id and not channel.is_public:
        raise NotVisible("channel")
    if not FileKey.of_channel(channel).matches(FileKey.of_file(write.rom_file)):
        raise FileMismatch("the ROM file does not match the channel's")
    return channel


async def _plan(write: SnapshotWrite, match_current: bool = True) -> _Plan:
    channel = _target_channel(write)
    owner = write.author
    if channel is not None and channel.user_id != owner.id:
        owner = db_user_handler.get_user(channel.user_id) or owner

    parent: Snapshot | None = None
    parent_content = StoredContent()
    if (parent_id := _parent_id(write)) is not None:
        parent = db_snapshot_handler.get_snapshot(parent_id)
        parent_channel = (
            db_snapshot_handler.get_channel(parent.channel_id)
            if parent and parent.channel_id
            else None
        )
        if parent is None or not _can_read(parent, write.author, parent_channel):
            raise NotVisible("parent snapshot")
        parent_content = db_snapshot_handler.get_stored_content(parent)
        await _hash_unhashed(parent_content)

    resolved = resolve(write.manifest, parent_content.resolved() if parent else None)
    current = (
        db_snapshot_handler.get_snapshot(channel.current_snapshot_id)
        if channel and channel.current_snapshot_id
        else None
    )
    plan = _Plan(owner=owner, channel=channel, parent=parent, resolved=resolved)
    if (
        match_current
        and current is not None
        and (
            current.digest == resolved.digest
            or await _clock_only(write, current, resolved)
        )
    ):
        plan.same_as = current.id
        return plan

    if parent_content.save and parent_content.save.content_hash:
        plan.saves[parent_content.save.content_hash] = parent_content.save
    if write.adopt_save is not None and write.adopt_save.content_hash:
        plan.saves[write.adopt_save.content_hash] = write.adopt_save
    for slots in parent_content.states.values():
        for state in slots.values():
            if state.content_hash:
                plan.states[state.content_hash] = state

    save_hashes = {resolved.save.hash} if resolved.save else set()
    plan.saves.update(
        db_snapshot_handler.get_saves_by_hash(
            owner.id, write.rom.id, save_hashes - plan.saves.keys()
        )
    )
    state_hashes = {h for slots in resolved.bank.values() for h in slots.values()}
    plan.states.update(
        db_snapshot_handler.get_states_by_hash(
            owner.id, write.rom.id, state_hashes - plan.states.keys()
        )
    )

    missing = []
    if resolved.save and resolved.save.hash not in plan.saves:
        if _content(write, SAVE_PART) is None:
            missing.append(SAVE_PART)
    uploaded = set(_state_parts(write, resolved))
    for core, bank_slots in resolved.bank.items():
        for slot, state_hash in bank_slots.items():
            if state_hash not in plan.states and state_hash not in uploaded:
                missing.append(state_part(core, slot))
    if missing:
        raise ContentMissing(missing)
    return plan


def _state_parts(write: SnapshotWrite, resolved: Resolved) -> dict[str, str]:
    """The part that carries each state hash; one part covers every slot holding it."""
    found: dict[str, str] = {}
    for core, slots in resolved.bank.items():
        for slot, state_hash in slots.items():
            key = state_part(core, slot)
            if _content(write, key) is not None:
                found.setdefault(state_hash, key)
    return found


async def _store_part(
    write: SnapshotWrite, plan: _Plan, key: str, expected_hash: str
) -> _StoredFile:
    part = write.parts[key]
    assert part.content is not None, "only parts that carry bytes are stored"
    is_save = key == SAVE_PART
    build_path = (
        fs_asset_handler.build_saves_file_path
        if is_save
        else fs_asset_handler.build_states_file_path
    )
    folder = build_path(
        user=plan.owner,
        platform_fs_slug=write.rom.platform.fs_slug,
        rom_id=write.rom.id,
        emulator=write.manifest.emulator,
    )
    file_name = sanitize_asset_filename(
        apply_datetime_tag(sanitize_asset_filename(part.file_name, "content")),
        "content",
    )
    await fs_asset_handler.write_file(
        file=part.content, path=folder, filename=file_name
    )
    path = f"{folder}/{file_name}"
    plan.written_paths.append(path)

    content_hash = await fs_asset_handler.compute_content_hash(path)
    if content_hash != expected_hash:
        raise ContentMismatch(key)

    common = {
        "file_name": file_name,
        "file_path": folder,
        "file_size_bytes": await fs_asset_handler.get_file_size(path),
        "content_hash": content_hash,
        "rom_id": write.rom.id,
        "user_id": plan.owner.id,
        "emulator": write.manifest.emulator,
        "emulator_version": write.manifest.emulator_version,
    }
    row: Save | State
    if is_save:
        entry = plan.resolved.save
        assert entry is not None
        row = Save(
            **common,
            identity_hash=await identity_hash_of_file(
                fs_asset_handler.validate_path(path)
            ),
            shape=entry.shape,
            format=entry.format,
            origin_device_id=write.origin_device_id or write.device_id,
            core=write.manifest.core,
            core_version=write.manifest.core_version,
        )
    else:
        _, core, _ = key.split(":", 2)
        ran = write.manifest.core
        row = State(
            **common,
            core=core,
            # The push names one core's version; a bank slot from another core has none.
            core_version=(
                write.manifest.core_version
                if ran and ran.lower() == core.lower()
                else None
            ),
        )
    stored = _StoredFile(row=row)

    if part.screenshot is not None:
        stored.screenshot = await _store_screenshot(
            write,
            plan,
            file_name,
            part.screenshot,
            part.screenshot_name,
            plan.written_paths,
        )
    return stored


async def _store_screenshot(
    write: SnapshotWrite,
    plan: _Plan,
    file_name: str,
    content: AssetContent,
    upload_name: str | None,
    written: list[str],
) -> Screenshot:
    """Write a screenshot named after the content row it belongs to."""
    stem = file_name.rsplit(".", 1)[0]
    extension = (upload_name or "screenshot.png").rsplit(".", 1)[-1]
    shot_name = sanitize_asset_filename(f"{stem}.{extension}", "screenshot")
    shot_folder = fs_asset_handler.build_screenshots_file_path(
        user=plan.owner,
        platform_fs_slug=write.rom.platform_slug,
        rom_id=write.rom.id,
    )
    await fs_asset_handler.write_file(
        file=content, path=shot_folder, filename=shot_name
    )
    shot_path = f"{shot_folder}/{shot_name}"
    written.append(shot_path)
    return Screenshot(
        file_name=shot_name,
        file_path=shot_folder,
        file_size_bytes=await fs_asset_handler.get_file_size(shot_path),
        rom_id=write.rom.id,
        user_id=plan.owner.id,
    )


async def _attach_screenshots(
    write: SnapshotWrite, plan: _Plan, stored: list[_StoredFile]
) -> list[Screenshot]:
    """Screenshots sent beside content the server already holds, for the rows
    that have none yet."""
    new_hashes = {file.row.content_hash for file in stored}
    wanted: list[tuple[str, bool, UploadPart]] = []
    for key, part in write.parts.items():
        if part.screenshot is None:
            continue
        if key == SAVE_PART:
            content_hash = plan.resolved.save.hash if plan.resolved.save else None
        else:
            _, core, slot = key.split(":", 2)
            content_hash = plan.resolved.bank.get(core, {}).get(slot)
        if content_hash and content_hash not in new_hashes:
            wanted.append((content_hash, key == SAVE_PART, part))
    if not wanted:
        return []

    saves = db_snapshot_handler.get_saves_by_hash(
        plan.owner.id, write.rom.id, {h for h, is_save, _ in wanted if is_save}
    )
    states = db_snapshot_handler.get_states_by_hash(
        plan.owner.id, write.rom.id, {h for h, is_save, _ in wanted if not is_save}
    )
    save_shots, state_shots = db_snapshot_handler.get_thumbnails(
        [row.id for row in saves.values()], [row.id for row in states.values()]
    )
    shots: list[Screenshot] = []
    attached: set[tuple[bool, int]] = set()
    for content_hash, is_save, part in wanted:
        row: Save | State | None = (saves if is_save else states).get(content_hash)
        if row is None or (is_save, row.id) in attached:
            continue
        if row.id in (save_shots if is_save else state_shots):
            continue
        assert part.screenshot is not None
        shot = await _store_screenshot(
            write,
            plan,
            row.file_name,
            part.screenshot,
            part.screenshot_name,
            plan.shot_paths,
        )
        if is_save:
            shot.save_id = row.id
        else:
            shot.state_id = row.id
        shot.is_public = row.is_public
        shots.append(shot)
        attached.add((is_save, row.id))
    return shots


async def _store_parts(write: SnapshotWrite, plan: _Plan) -> list[_StoredFile]:
    """Write every part whose hash the server lacks; parts it already holds are ignored."""
    stored: list[_StoredFile] = []
    resolved = plan.resolved
    if resolved.save and resolved.save.hash not in plan.saves:
        stored.append(await _store_part(write, plan, SAVE_PART, resolved.save.hash))
    for state_hash, key in _state_parts(write, resolved).items():
        if state_hash not in plan.states:
            stored.append(await _store_part(write, plan, key, state_hash))
    return stored


def _lock_or_create_channel(write: SnapshotWrite, session: Session) -> Channel | None:
    target = write.channel
    if target is None:
        return None
    if target.id is not None:
        channel = db_snapshot_handler.lock_channel(target.id, session=session)
        if channel is not None:
            return channel
    assert write.rom_file is not None and target.label
    channel = Channel(
        user_id=write.author.id,
        rom_id=write.rom.id,
        platform_id=write.rom.platform_id,
        label=target.label,
        **FileKey.of_file(write.rom_file).channel_columns(),
    )
    if target.id is not None:
        channel.id = target.id
    session.add(channel)
    session.flush()
    return channel


def _commit(
    write: SnapshotWrite,
    plan: _Plan,
    stored: list[_StoredFile],
    shots: list[Screenshot],
    session: Session,
) -> WriteResult:
    session.add_all(shots)
    channel = _lock_or_create_channel(write, session)
    digest = plan.resolved.digest
    current = (
        session.get(Snapshot, channel.current_snapshot_id)
        if channel and channel.current_snapshot_id
        else None
    )

    if plan.unchanged and (current is None or current.id != plan.same_as):
        raise _CurrentMoved
    if (
        channel is not None
        and current is not None
        and (plan.unchanged or current.digest == digest)
    ):
        if write.device_id:
            db_snapshot_handler.record_device_base(
                write.device_id, channel.id, current.id, session=session
            )
        return WriteResult(snapshot=current, outcome=Outcome.UNCHANGED, current=current)

    kind = SnapshotKind.ARCHIVAL
    if channel is not None:
        assert write.channel is not None
        stale = channel.current_snapshot_id != write.channel.expected_current_id
        kind = SnapshotKind.BRANCH if stale else SnapshotKind.CHANNEL
        if (
            kind == SnapshotKind.CHANNEL
            and channel.is_hardcore
            and not write.manifest.is_hardcore
            and not write.manifest.approve_hardcore_downgrade
        ):
            raise HardcoreDowngrade("the channel's current save is hardcore")

    for file in stored:
        file.row.channel_id = channel.id if channel else None
        session.add(file.row)
    session.flush()
    for file in stored:
        if isinstance(file.row, Save) and file.row.content_hash:
            plan.saves[file.row.content_hash] = file.row
        elif isinstance(file.row, State) and file.row.content_hash:
            plan.states[file.row.content_hash] = file.row
        if file.screenshot is not None:
            if isinstance(file.row, Save):
                file.screenshot.save_id = file.row.id
            else:
                file.screenshot.state_id = file.row.id
            session.add(file.screenshot)

    resolved = plan.resolved
    snapshot = Snapshot(
        user_id=plan.owner.id,
        author_user_id=write.author.id,
        rom_id=write.rom.id,
        channel_id=channel.id if channel else None,
        parent_snapshot_id=plan.parent.id if plan.parent else None,
        kind=kind,
        is_public=write.is_public if kind == SnapshotKind.ARCHIVAL else False,
        save_id=plan.saves[resolved.save.hash].id if resolved.save else None,
        digest=digest,
        rom_sha1=(
            channel.target_file_hash
            if channel
            else write.rom_file.sha1_hash if write.rom_file else None
        ),
        is_hardcore=write.manifest.is_hardcore,
        save_target=write.rom.save_target,
        emulator=write.manifest.emulator,
        origin_device_id=write.origin_device_id or write.device_id,
    )
    snapshot.states = [
        SnapshotState(core=core, slot=slot, state_id=plan.states[state_hash].id)
        for core, slots in resolved.bank.items()
        for slot, state_hash in slots.items()
    ]
    session.add(snapshot)
    session.flush()

    if (channel is not None and channel.is_public) or snapshot.is_public:
        db_snapshot_handler.sync_content_visibility(
            [snapshot.save_id] if snapshot.save_id else [],
            [entry.state_id for entry in snapshot.states],
            session=session,
        )

    if channel is None:
        return WriteResult(snapshot=snapshot, outcome=Outcome.CREATED, current=None)
    if kind == SnapshotKind.BRANCH:
        return WriteResult(snapshot=snapshot, outcome=Outcome.BRANCHED, current=current)

    channel.current_snapshot_id = snapshot.id
    channel.is_hardcore = write.manifest.is_hardcore
    if write.device_id:
        db_snapshot_handler.record_device_base(
            write.device_id, channel.id, snapshot.id, session=session
        )
    return WriteResult(snapshot=snapshot, outcome=Outcome.CREATED, current=snapshot)


async def write_snapshot(write: SnapshotWrite) -> WriteResult:
    """Store a push's new content and its snapshot, and move the channel's pointer.

    Raises:
        SnapshotWriteError: the push is refused; see its subclasses.
    """
    try:
        return await _write(write, match_current=True)
    except _CurrentMoved:
        return await _write(write, match_current=False)


async def _write(write: SnapshotWrite, match_current: bool) -> WriteResult:
    plan = await _plan(write, match_current)
    try:
        stored = [] if plan.unchanged else await _store_parts(write, plan)
        shots = await _attach_screenshots(write, plan, stored)
        with sync_session.begin() as session:
            result = _commit(write, plan, stored, shots, session)
    except BaseException:
        for path in [*plan.written_paths, *plan.shot_paths]:
            await remove_asset_file(path, "Snapshot content")
        raise
    # Another push landed the same content between the plan and the lock.
    if result.outcome == Outcome.UNCHANGED:
        for path in plan.written_paths:
            await remove_asset_file(path, "Snapshot content")
    if result.outcome == Outcome.CREATED and result.snapshot.channel_id:
        await retention.prune(result.snapshot.channel_id)
    return result
