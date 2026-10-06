import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    ColumnElement,
    and_,
    delete,
    exists,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.orm import Session

from decorators.database import INJECTED_SESSION, begin_session
from handler.snapshots.file_key import FileKey
from handler.snapshots.legacy import channel_label, may_load, sync_key
from handler.snapshots.manifest import Resolved, SaveEntry
from models.assets import Save, SaveFormat, Screenshot, State
from models.channel import Channel
from models.device import Device
from models.device_channel_sync import DeviceChannelSync
from models.rom import Rom, RomFile
from models.snapshot import Snapshot, SnapshotKind, SnapshotState

from .base_handler import DBBaseHandler


@dataclass
class ReleasedContent:
    """Rows deleted with the snapshots that held them, whose files the caller removes."""

    saves: list[Save] = field(default_factory=list)
    states: list[State] = field(default_factory=list)
    screenshots: list[Screenshot] = field(default_factory=list)


@dataclass
class StoredContent:
    """A snapshot's content rows, keyed the way its manifest is."""

    save: Save | None = None
    states: dict[str, dict[str, State]] = field(default_factory=dict)

    def resolved(self) -> Resolved:
        save = (
            SaveEntry(
                hash=self.save.content_hash or "",
                shape=self.save.shape,
                format=self.save.format,
            )
            if self.save
            else None
        )
        bank = {
            core: {slot: state.content_hash or "" for slot, state in slots.items()}
            for core, slots in self.states.items()
        }
        return Resolved(save=save, bank=bank)


def _keyed_to(key: FileKey) -> ColumnElement[bool]:
    """Channels keyed to this file, in SQL, as `FileKey.matches` decides in Python."""
    by_name = and_(
        Channel.target_file_name == key.name,
        Channel.target_file_size == key.size,
    )
    if not key.sha1:
        return by_name
    # A channel made before the file was hashed is still keyed by name.
    return or_(
        Channel.target_file_hash == key.sha1,
        and_(Channel.target_file_hash.is_(None), by_name),
    )


def link_channels_to_files(
    session: Session, rom_id: int, platform_id: int, files: Sequence[RomFile]
) -> None:
    """After a scan: reattach detached channels whose file is back, and rekey
    the ROM's name-keyed channels to a hash the scan just computed."""
    for rom_file in files:
        key = FileKey.of_file(rom_file)
        detached = session.scalars(
            select(Channel).where(
                Channel.rom_id.is_(None),
                Channel.platform_id == platform_id,
                _keyed_to(key),
            )
        ).all()
        for channel in detached:
            channel.rom_id = rom_id
            for model in (Snapshot, Save, State):
                session.execute(
                    update(model)
                    .where(model.channel_id == channel.id, model.rom_id.is_(None))
                    .values(rom_id=rom_id)
                    .execution_options(synchronize_session=False)
                )
        if key.sha1:
            session.execute(
                update(Channel)
                .where(
                    Channel.rom_id == rom_id,
                    Channel.target_file_hash.is_(None),
                    Channel.target_file_name == key.name,
                    Channel.target_file_size == key.size,
                )
                .values(target_file_hash=key.sha1)
                .execution_options(synchronize_session=False)
            )


def channel_for_slot(
    session: Session, user_id: int, rom_id: int, slot: str
) -> uuid.UUID | None:
    """The channel a legacy upload to `slot` files its save under, created on
    first use. A slot already linked keeps its channel, renamed or not."""
    label = channel_label(slot)
    if label is None:
        return None
    existing = _find_channel_for_slot(session, user_id, rom_id, slot, label)
    if existing is not None:
        return existing
    platform_id = session.scalar(select(Rom.platform_id).where(Rom.id == rom_id))
    key = sync_key(session.scalars(select(RomFile).where(RomFile.rom_id == rom_id)))
    if platform_id is None or key is None:
        return None
    channel = Channel(
        user_id=user_id,
        rom_id=rom_id,
        platform_id=platform_id,
        label=label,
        **key.channel_columns(),
    )
    session.add(channel)
    session.flush()
    return channel.id


def _find_channel_for_slot(
    session: Session, user_id: int, rom_id: int, slot: str, label: str
) -> uuid.UUID | None:
    linked = session.scalar(
        select(Save.channel_id)
        .where(
            Save.user_id == user_id,
            Save.rom_id == rom_id,
            Save.slot == slot,
            Save.channel_id.is_not(None),
        )
        .order_by(Save.updated_at.desc())
        .limit(1)
    )
    if linked is not None:
        return linked

    platform_id = session.scalar(select(Rom.platform_id).where(Rom.id == rom_id))
    key = sync_key(session.scalars(select(RomFile).where(RomFile.rom_id == rom_id)))
    if platform_id is None or key is None:
        return None
    return session.scalar(
        select(Channel.id)
        .where(
            Channel.user_id == user_id,
            Channel.platform_id == platform_id,
            # Clients vary a slot's case; MariaDB's collation ignores it, PostgreSQL's doesn't.
            func.lower(Channel.label) == label.lower(),
            _keyed_to(key),
        )
        .order_by(Channel.created_at)
        .limit(1)
    )


class DBSnapshotsHandler(DBBaseHandler):
    @begin_session
    def current_saves_for_slots(
        self,
        user_id: int,
        slots: Collection[tuple[int, str]],
        emulators: Collection[str | None] | None = None,
        cores: Collection[str | None] | None = None,
        session: Session = INJECTED_SESSION,
    ) -> dict[tuple[int, str], Save]:
        """The current snapshot's save of each legacy slot's channel, keyed by
        (rom_id, slot), for channels a snapshot client keeps. Neutral saves are
        left out, since a legacy client cannot load them, and so is a save the
        client's `cores` or `emulators` rule out (see `may_load`)."""
        rom_ids = {rom_id for rom_id, _ in slots}
        if not rom_ids:
            return {}
        kept = set(
            session.scalars(
                select(Channel.rom_id).where(
                    Channel.user_id == user_id,
                    Channel.rom_id.in_(rom_ids),
                    Channel.current_snapshot_id.is_not(None),
                )
            )
        )
        heads: dict[tuple[int, str], Save] = {}
        for rom_id, slot in slots:
            label = channel_label(slot)
            if rom_id not in kept or label is None:
                continue
            channel_id = _find_channel_for_slot(session, user_id, rom_id, slot, label)
            if channel_id is None:
                continue
            save = session.scalar(
                select(Save)
                .join(Snapshot, Snapshot.save_id == Save.id)
                .join(Channel, Channel.current_snapshot_id == Snapshot.id)
                .where(
                    Channel.id == channel_id,
                    or_(Save.format.is_(None), Save.format == SaveFormat.NATIVE),
                )
            )
            if save is None or not may_load(save, emulators, cores):
                continue
            heads[(rom_id, slot)] = save
        return heads

    @begin_session
    def get_snapshot(
        self, id: int, session: Session = INJECTED_SESSION
    ) -> Snapshot | None:
        return session.get(Snapshot, id)

    @begin_session
    def get_channel(
        self, id: uuid.UUID, session: Session = INJECTED_SESSION
    ) -> Channel | None:
        return session.get(Channel, id)

    @begin_session
    def lock_channel(
        self, id: uuid.UUID, session: Session = INJECTED_SESSION
    ) -> Channel | None:
        """The channel, locked until the caller's transaction ends."""
        return session.scalar(select(Channel).where(Channel.id == id).with_for_update())

    @begin_session
    def get_stored_content(
        self, snapshot: Snapshot, session: Session = INJECTED_SESSION
    ) -> StoredContent:
        content = StoredContent(
            save=session.get(Save, snapshot.save_id) if snapshot.save_id else None
        )
        rows = session.execute(
            select(SnapshotState, State)
            .join(State, SnapshotState.state_id == State.id)
            .where(SnapshotState.snapshot_id == snapshot.id)
        ).all()
        for entry, state in rows:
            content.states.setdefault(entry.core, {})[entry.slot] = state
        return content

    @begin_session
    def get_saves_by_hash(
        self,
        user_id: int,
        rom_id: int,
        hashes: Collection[str],
        session: Session = INJECTED_SESSION,
    ) -> dict[str, Save]:
        if not hashes:
            return {}
        rows = session.scalars(
            select(Save)
            .where(
                Save.user_id == user_id,
                Save.rom_id == rom_id,
                Save.content_hash.in_(hashes),
                # A row no snapshot holds may still be overwritten by a legacy writer.
                exists().where(Snapshot.save_id == Save.id),
            )
            .order_by(Save.id)
        )
        found: dict[str, Save] = {}
        for save in rows:
            if save.content_hash:
                found.setdefault(save.content_hash, save)
        return found

    @begin_session
    def get_states_by_hash(
        self,
        user_id: int,
        rom_id: int,
        hashes: Collection[str],
        session: Session = INJECTED_SESSION,
    ) -> dict[str, State]:
        if not hashes:
            return {}
        rows = session.scalars(
            select(State)
            .where(
                State.user_id == user_id,
                State.rom_id == rom_id,
                State.content_hash.in_(hashes),
                exists().where(SnapshotState.state_id == State.id),
            )
            .order_by(State.id)
        )
        found: dict[str, State] = {}
        for state in rows:
            if state.content_hash:
                found.setdefault(state.content_hash, state)
        return found

    @begin_session
    def get_channels_for_file(
        self,
        user_id: int,
        platform_id: int,
        key: FileKey,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[Channel]:
        """The user's channels on a file: by hash, or by name and size for unhashed ones."""
        return session.scalars(
            select(Channel)
            .where(
                Channel.user_id == user_id,
                Channel.platform_id == platform_id,
                _keyed_to(key),
            )
            .order_by(Channel.updated_at.desc())
        ).all()

    @begin_session
    def get_channels_for_rom(
        self, rom_id: int, user_id: int, session: Session = INJECTED_SESSION
    ) -> Sequence[Channel]:
        """The user's channels on a ROM, then other users' public ones."""
        return session.scalars(
            select(Channel)
            .where(
                Channel.rom_id == rom_id,
                or_(Channel.user_id == user_id, Channel.is_public.is_(True)),
            )
            .order_by((Channel.user_id != user_id), Channel.updated_at.desc())
        ).all()

    @begin_session
    def get_detached_channels(
        self, user_id: int, platform_id: int, session: Session = INJECTED_SESSION
    ) -> Sequence[Channel]:
        """The user's channels on a platform whose ROM was removed and no scan
        has found again."""
        return session.scalars(
            select(Channel)
            .where(
                Channel.user_id == user_id,
                Channel.platform_id == platform_id,
                Channel.rom_id.is_(None),
            )
            .order_by(Channel.updated_at.desc())
        ).all()

    @begin_session
    def attach_channel(
        self,
        channel_id: uuid.UUID,
        rom_file: RomFile,
        session: Session = INJECTED_SESSION,
    ) -> Channel:
        """Key a detached channel to `rom_file` and bring its content back to
        that file's ROM."""
        channel = session.get_one(Channel, channel_id)
        channel.rom_id = rom_file.rom_id
        for column, value in FileKey.of_file(rom_file).channel_columns().items():
            setattr(channel, column, value)
        for model in (Snapshot, Save, State):
            session.execute(
                update(model)
                .where(model.channel_id == channel_id, model.rom_id.is_(None))
                .values(rom_id=rom_file.rom_id)
                .execution_options(synchronize_session=False)
            )
        session.flush()
        return channel

    @begin_session
    def count_snapshots(
        self, channel_id: uuid.UUID, session: Session = INJECTED_SESSION
    ) -> int:
        return (
            session.scalar(
                select(func.count(Snapshot.id)).where(Snapshot.channel_id == channel_id)
            )
            or 0
        )

    @begin_session
    def add_channel(
        self, channel: Channel, session: Session = INJECTED_SESSION
    ) -> Channel:
        session.add(channel)
        session.flush()
        return channel

    @begin_session
    def get_channel_history(
        self,
        channel_id: uuid.UUID,
        limit: int,
        before_id: int | None = None,
        save_target: str | None = None,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[Snapshot]:
        query = select(Snapshot).where(Snapshot.channel_id == channel_id)
        if before_id is not None:
            query = query.where(Snapshot.id < before_id)
        if save_target is not None:
            query = query.where(Snapshot.save_target == save_target)
        return session.scalars(query.order_by(Snapshot.id.desc()).limit(limit)).all()

    @begin_session
    def get_holders(
        self,
        snapshot_id: int,
        user_id: int,
        session: Session = INJECTED_SESSION,
    ) -> Sequence[tuple[DeviceChannelSync, Device]]:
        """The user's own devices whose last sync in the channel was this snapshot."""
        rows = session.execute(
            select(DeviceChannelSync, Device)
            .join(Device, DeviceChannelSync.device_id == Device.id)
            .where(
                DeviceChannelSync.base_snapshot_id == snapshot_id,
                Device.user_id == user_id,
            )
            .order_by(DeviceChannelSync.synced_at.desc())
        ).all()
        return [(sync, device) for sync, device in rows]

    @begin_session
    def get_thumbnails(
        self,
        save_ids: Collection[int],
        state_ids: Collection[int],
        session: Session = INJECTED_SESSION,
    ) -> tuple[dict[int, Screenshot], dict[int, Screenshot]]:
        """Screenshots linked to these saves and states, by row id."""
        by_save: dict[int, Screenshot] = {}
        by_state: dict[int, Screenshot] = {}
        if not save_ids and not state_ids:
            return by_save, by_state
        rows = session.scalars(
            select(Screenshot).where(
                or_(
                    Screenshot.save_id.in_(save_ids),
                    Screenshot.state_id.in_(state_ids),
                )
            )
        )
        for shot in rows:
            if shot.save_id is not None:
                by_save[shot.save_id] = shot
            if shot.state_id is not None:
                by_state[shot.state_id] = shot
        return by_save, by_state

    @begin_session
    def get_channel_file(
        self, channel: Channel, session: Session = INJECTED_SESSION
    ) -> RomFile | None:
        """The library file a channel is keyed to today, if its ROM still holds one."""
        if channel.rom_id is None:
            return None
        key = FileKey.of_channel(channel)
        for rom_file in session.scalars(
            select(RomFile).where(RomFile.rom_id == channel.rom_id).order_by(RomFile.id)
        ):
            if key.matches(FileKey.of_file(rom_file)):
                return rom_file
        return None

    @begin_session
    def sync_content_visibility(
        self,
        save_ids: Collection[int],
        state_ids: Collection[int],
        session: Session = INJECTED_SESSION,
    ) -> None:
        """Set each row and its screenshot public exactly when a public channel or
        public archival snapshot holds the row, so the content routes serve it
        to other users."""
        shared = or_(
            Channel.is_public.is_(True),
            and_(Snapshot.kind == SnapshotKind.ARCHIVAL, Snapshot.is_public.is_(True)),
        )
        public_saves = set(
            session.scalars(
                select(Snapshot.save_id)
                .outerjoin(Channel, Snapshot.channel_id == Channel.id)
                .where(Snapshot.save_id.in_(save_ids), shared)
            )
        )
        public_states = set(
            session.scalars(
                select(SnapshotState.state_id)
                .join(Snapshot, SnapshotState.snapshot_id == Snapshot.id)
                .outerjoin(Channel, Snapshot.channel_id == Channel.id)
                .where(SnapshotState.state_id.in_(state_ids), shared)
            )
        )
        for save_id in save_ids:
            session.get_one(Save, save_id).is_public = save_id in public_saves
        for state_id in state_ids:
            session.get_one(State, state_id).is_public = state_id in public_states
        for column, ids, public in (
            (Screenshot.save_id, save_ids, public_saves),
            (Screenshot.state_id, state_ids, public_states),
        ):
            if ids:
                session.execute(
                    update(Screenshot)
                    .where(column.in_(ids))
                    .values(is_public=column.in_(public))
                    .execution_options(synchronize_session=False)
                )
        session.flush()

    @begin_session
    def get_content_ids(
        self, channel_id: uuid.UUID, session: Session = INJECTED_SESSION
    ) -> tuple[set[int], set[int]]:
        """Every save and state row a channel's snapshots hold."""
        save_ids = set(
            session.scalars(
                select(Snapshot.save_id).where(
                    Snapshot.channel_id == channel_id, Snapshot.save_id.is_not(None)
                )
            )
        )
        state_ids = set(
            session.scalars(
                select(SnapshotState.state_id)
                .join(Snapshot, SnapshotState.snapshot_id == Snapshot.id)
                .where(Snapshot.channel_id == channel_id)
            )
        )
        return {i for i in save_ids if i is not None}, state_ids

    def _archival_holding(
        self, session: Session, save_id: int | None, state_id: int | None
    ) -> Sequence[Snapshot]:
        query = select(Snapshot).where(Snapshot.kind == SnapshotKind.ARCHIVAL)
        if save_id is not None:
            return session.scalars(query.where(Snapshot.save_id == save_id)).all()
        return session.scalars(
            query.join(SnapshotState, SnapshotState.snapshot_id == Snapshot.id).where(
                SnapshotState.state_id == state_id
            )
        ).all()

    @begin_session
    def release_backup(
        self,
        save_id: int | None = None,
        state_id: int | None = None,
        session: Session = INJECTED_SESSION,
    ) -> None:
        """Take a backup row out of the archival snapshots holding it, so it can be
        deleted. A snapshot left with nothing is deleted with it."""
        for snapshot in self._archival_holding(session, save_id, state_id):
            if save_id is not None:
                snapshot.save_id = None
            else:
                session.execute(
                    delete(SnapshotState).where(
                        SnapshotState.snapshot_id == snapshot.id,
                        SnapshotState.state_id == state_id,
                    )
                )
            session.flush()
            session.refresh(snapshot)
            content = self.get_stored_content(snapshot, session=session)
            if content.save is None and not content.states:
                session.delete(snapshot)
            else:
                snapshot.digest = content.resolved().digest
        session.flush()

    @begin_session
    def refresh_backup_digests(
        self,
        save_id: int | None = None,
        state_id: int | None = None,
        session: Session = INJECTED_SESSION,
    ) -> None:
        """Recompute the digest of each archival snapshot holding a backup whose bytes changed."""
        for snapshot in self._archival_holding(session, save_id, state_id):
            snapshot.digest = (
                self.get_stored_content(snapshot, session=session).resolved().digest
            )
        session.flush()

    def _delete_snapshots(
        self, session: Session, ids: Sequence[int]
    ) -> ReleasedContent:
        """Delete snapshots, then the content rows only they held, with their
        screenshots. A legacy row is never held by a snapshot, so never taken."""
        if not ids:
            return ReleasedContent()
        save_ids = set(
            session.scalars(
                select(Snapshot.save_id).where(
                    Snapshot.id.in_(ids), Snapshot.save_id.is_not(None)
                )
            )
        )
        state_ids = set(
            session.scalars(
                select(SnapshotState.state_id).where(SnapshotState.snapshot_id.in_(ids))
            )
        )
        session.execute(
            delete(Snapshot)
            .where(Snapshot.id.in_(ids))
            .execution_options(synchronize_session=False)
        )
        released = ReleasedContent(
            saves=list(
                session.scalars(
                    select(Save).where(
                        Save.id.in_(save_ids),
                        ~exists().where(Snapshot.save_id == Save.id),
                    )
                )
            ),
            states=list(
                session.scalars(
                    select(State).where(
                        State.id.in_(state_ids),
                        ~exists().where(SnapshotState.state_id == State.id),
                    )
                )
            ),
        )
        save_shots, state_shots = self.get_thumbnails(
            [save.id for save in released.saves],
            [state.id for state in released.states],
            session=session,
        )
        released.screenshots = [*save_shots.values(), *state_shots.values()]
        for model, rows in (
            (Screenshot, released.screenshots),
            (Save, released.saves),
            (State, released.states),
        ):
            if rows:
                session.execute(
                    delete(model)
                    .where(model.id.in_([row.id for row in rows]))
                    .execution_options(synchronize_session=False)
                )
        return released

    @begin_session
    def prune_channel(
        self, channel_id: uuid.UUID, keep: int, session: Session = INJECTED_SESSION
    ) -> ReleasedContent:
        """Delete the channel's snapshots past its newest `keep`. The current and
        pinned snapshots always stay, pinned ones uncounted; a detached channel
        keeps everything."""
        channel = session.get(Channel, channel_id, with_for_update=True)
        if channel is None or channel.rom_id is None:
            return ReleasedContent()
        candidates = session.scalars(
            select(Snapshot.id)
            .where(
                Snapshot.channel_id == channel_id,
                Snapshot.kind == SnapshotKind.CHANNEL,
                Snapshot.is_pinned.is_(False),
            )
            .order_by(Snapshot.id.desc())
        ).all()
        doomed = [id for id in candidates[keep:] if id != channel.current_snapshot_id]
        return self._delete_snapshots(session, doomed)

    @begin_session
    def prune_branches(
        self, older_than: datetime, session: Session = INJECTED_SESSION
    ) -> ReleasedContent:
        """Delete branches created before `older_than`, except in detached channels."""
        doomed = session.scalars(
            select(Snapshot.id)
            .join(Channel, Snapshot.channel_id == Channel.id)
            .where(
                Snapshot.kind == SnapshotKind.BRANCH,
                Snapshot.is_pinned.is_(False),
                Snapshot.created_at < older_than,
                Channel.rom_id.is_not(None),
            )
        ).all()
        return self._delete_snapshots(session, doomed)

    @begin_session
    def update_channel(
        self,
        id: uuid.UUID,
        data: dict[str, Any],
        session: Session = INJECTED_SESSION,
    ) -> Channel:
        channel = session.get_one(Channel, id)
        for key, value in data.items():
            setattr(channel, key, value)
        session.flush()
        return channel

    @begin_session
    def delete_channel(
        self, id: uuid.UUID, session: Session = INJECTED_SESSION
    ) -> ReleasedContent:
        """Delete a channel, keeping its current and pinned snapshots as archival.
        Legacy saves filed under it lose the link and become backups."""
        channel = session.get_one(Channel, id, with_for_update=True)
        kept = session.scalars(
            select(Snapshot).where(
                Snapshot.channel_id == id,
                or_(
                    Snapshot.id == channel.current_snapshot_id,
                    Snapshot.is_pinned.is_(True),
                ),
            )
        ).all()
        for snapshot in kept:
            snapshot.channel_id = None
            snapshot.kind = SnapshotKind.ARCHIVAL
            snapshot.is_public = channel.is_public
        channel.current_snapshot_id = None
        session.flush()
        released = self._delete_snapshots(
            session,
            session.scalars(select(Snapshot.id).where(Snapshot.channel_id == id)).all(),
        )
        session.delete(channel)
        session.flush()
        return released

    @begin_session
    def update_snapshot(
        self,
        id: int,
        data: dict[str, Any],
        session: Session = INJECTED_SESSION,
    ) -> Snapshot:
        snapshot = session.get_one(Snapshot, id)
        for key, value in data.items():
            setattr(snapshot, key, value)
        session.flush()
        return snapshot

    @begin_session
    def record_device_base(
        self,
        device_id: str,
        channel_id: uuid.UUID,
        snapshot_id: int,
        session: Session = INJECTED_SESSION,
    ) -> DeviceChannelSync:
        now = datetime.now(timezone.utc)
        sync = session.get(DeviceChannelSync, (device_id, channel_id))
        if sync is None:
            sync = DeviceChannelSync(device_id=device_id, channel_id=channel_id)
            session.add(sync)
        sync.base_snapshot_id = snapshot_id
        sync.synced_at = now
        session.flush()
        return sync

    @begin_session
    def is_frozen(
        self,
        save_id: int | None = None,
        state_id: int | None = None,
        session: Session = INJECTED_SESSION,
    ) -> bool:
        """Whether a channel or branch snapshot holds the row, so its bytes must not change."""
        held = (SnapshotKind.CHANNEL, SnapshotKind.BRANCH)
        query = select(Snapshot.id).where(Snapshot.kind.in_(held))
        if save_id is not None:
            query = query.where(Snapshot.save_id == save_id)
        else:
            query = query.join(
                SnapshotState, SnapshotState.snapshot_id == Snapshot.id
            ).where(SnapshotState.state_id == state_id)
        return session.scalar(query.limit(1)) is not None
