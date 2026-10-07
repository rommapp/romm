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
from models.snapshot import Snapshot, SnapshotKind, SnapshotPin, SnapshotState

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

    @property
    def state_rows(self) -> list[State]:
        """Every state the bank holds, across cores and slots."""
        return [state for slots in self.states.values() for state in slots.values()]

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
    keys = [FileKey.of_file(rom_file) for rom_file in files]
    if not keys:
        return
    candidates = session.scalars(
        select(Channel).where(
            or_(
                and_(Channel.rom_id.is_(None), Channel.platform_id == platform_id),
                and_(Channel.rom_id == rom_id, Channel.target_file_hash.is_(None)),
            )
        )
    ).all()
    for channel in candidates:
        channel_key = FileKey.of_channel(channel)
        matches = [key for key in keys if channel_key.matches(key)]
        if not matches:
            continue
        if channel.rom_id is None:
            channel.rom_id = rom_id
            for model in (Snapshot, Save, State):
                session.execute(
                    update(model)
                    .where(model.channel_id == channel.id, model.rom_id.is_(None))
                    .values(rom_id=rom_id)
                    .execution_options(synchronize_session=False)
                )
        if channel.target_file_hash is None:
            hashed = next((key.sha1 for key in matches if key.sha1), None)
            if hashed:
                channel.target_file_hash = hashed


def channel_for_slot(
    session: Session, user_id: int, rom_id: int, slot: str, create: bool = True
) -> uuid.UUID | None:
    """The channel a legacy upload to `slot` files its save under, created on
    first use when `create` is set. A slot already linked keeps its channel,
    renamed or not."""
    label = channel_label(slot)
    if label is None:
        return None
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
    existing = session.scalar(
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
    if existing is not None or not create:
        return existing
    channel = key.new_channel(user_id, rom_id, platform_id, label)
    session.add(channel)
    session.flush()
    return channel.id


_FREEZING_KINDS = (SnapshotKind.CHANNEL, SnapshotKind.BRANCH)
_PINNED = exists().where(SnapshotPin.snapshot_id == Snapshot.id)


def held_save_ids(session: Session, save_ids: Collection[int]) -> set[int]:
    if not save_ids:
        return set()
    return set(
        session.scalars(
            select(Snapshot.save_id).where(Snapshot.save_id.in_(save_ids)).distinct()
        )
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
        """The current save of each legacy slot's channel by (rom_id, slot),
        leaving out neutral saves and any `may_load` rules out for the client."""
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
            if rom_id not in kept:
                continue
            channel_id = channel_for_slot(session, user_id, rom_id, slot, create=False)
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
        return self.get_stored_contents([snapshot], session=session)[snapshot.id]

    @begin_session
    def get_stored_contents(
        self, snapshots: Sequence[Snapshot], session: Session = INJECTED_SESSION
    ) -> dict[int, StoredContent]:
        """Each snapshot's content rows, in two queries however many there are."""
        save_ids = {s.save_id for s in snapshots if s.save_id is not None}
        saves = (
            {
                save.id: save
                for save in session.scalars(select(Save).where(Save.id.in_(save_ids)))
            }
            if save_ids
            else {}
        )
        contents = {
            s.id: StoredContent(save=saves.get(s.save_id) if s.save_id else None)
            for s in snapshots
        }
        if not contents:
            return contents
        rows = session.execute(
            select(SnapshotState, State)
            .join(State, SnapshotState.state_id == State.id)
            .where(SnapshotState.snapshot_id.in_(contents.keys()))
        ).all()
        for entry, state in rows:
            contents[entry.snapshot_id].states.setdefault(entry.core, {})[
                entry.slot
            ] = state
        return contents

    @begin_session
    def get_saves_by_hash(
        self,
        user_id: int,
        rom_id: int,
        hashes: Collection[str],
        channel_id: uuid.UUID | None = None,
        session: Session = INJECTED_SESSION,
    ) -> dict[str, Save]:
        """The user's snapshot-held saves on a ROM by content hash, only those
        `channel_id`'s snapshots hold when given."""
        if not hashes:
            return {}
        # A row no snapshot holds may still be overwritten by a legacy writer.
        held = exists().where(Snapshot.save_id == Save.id)
        if channel_id is not None:
            held = held.where(Snapshot.channel_id == channel_id)
        rows = session.scalars(
            select(Save)
            .where(
                Save.user_id == user_id,
                Save.rom_id == rom_id,
                Save.content_hash.in_(hashes),
                held,
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
        channel_id: uuid.UUID | None = None,
        session: Session = INJECTED_SESSION,
    ) -> dict[str, State]:
        """The user's snapshot-held states on a ROM by content hash, only those
        `channel_id`'s snapshots hold when given."""
        if not hashes:
            return {}
        held = exists().where(SnapshotState.state_id == State.id)
        if channel_id is not None:
            held = held.where(
                SnapshotState.snapshot_id.in_(
                    select(Snapshot.id).where(Snapshot.channel_id == channel_id)
                )
            )
        rows = session.scalars(
            select(State)
            .where(
                State.user_id == user_id,
                State.rom_id == rom_id,
                State.content_hash.in_(hashes),
                held,
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
    def count_snapshots_by_channel(
        self, channel_ids: Collection[uuid.UUID], session: Session = INJECTED_SESSION
    ) -> dict[uuid.UUID, int]:
        if not channel_ids:
            return {}
        rows = session.execute(
            select(Snapshot.channel_id, func.count(Snapshot.id))
            .where(Snapshot.channel_id.in_(channel_ids))
            .group_by(Snapshot.channel_id)
        ).all()
        return {channel_id: count for channel_id, count in rows if channel_id}

    @begin_session
    def get_snapshots(
        self, ids: Collection[int], session: Session = INJECTED_SESSION
    ) -> dict[int, Snapshot]:
        if not ids:
            return {}
        return {
            snapshot.id: snapshot
            for snapshot in session.scalars(
                select(Snapshot).where(Snapshot.id.in_(ids))
            )
        }

    @begin_session
    def get_devices(
        self, ids: Collection[str], session: Session = INJECTED_SESSION
    ) -> dict[str, Device]:
        if not ids:
            return {}
        return {
            device.id: device
            for device in session.scalars(select(Device).where(Device.id.in_(ids)))
        }

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
    def get_holders_by_snapshot(
        self,
        snapshot_ids: Collection[int],
        user_id: int,
        session: Session = INJECTED_SESSION,
    ) -> dict[int, list[tuple[DeviceChannelSync, Device]]]:
        """The user's own devices whose last sync in the channel was each
        snapshot, by snapshot id, in one query."""
        if not snapshot_ids:
            return {}
        rows = session.execute(
            select(DeviceChannelSync, Device)
            .join(Device, DeviceChannelSync.device_id == Device.id)
            .where(
                DeviceChannelSync.base_snapshot_id.in_(snapshot_ids),
                Device.user_id == user_id,
            )
            .order_by(DeviceChannelSync.synced_at.desc())
        ).all()
        holders: dict[int, list[tuple[DeviceChannelSync, Device]]] = {}
        for sync, device in rows:
            if sync.base_snapshot_id is not None:
                holders.setdefault(sync.base_snapshot_id, []).append((sync, device))
        return holders

    @begin_session
    def get_pins(
        self,
        snapshot_ids: Collection[int],
        user_id: int,
        session: Session = INJECTED_SESSION,
    ) -> tuple[dict[int, int], set[int]]:
        """How many users pinned each snapshot, and which of them `user_id` pinned."""
        if not snapshot_ids:
            return {}, set()
        rows = session.execute(
            select(SnapshotPin.snapshot_id, SnapshotPin.user_id).where(
                SnapshotPin.snapshot_id.in_(snapshot_ids)
            )
        ).all()
        counts: dict[int, int] = {}
        mine: set[int] = set()
        for snapshot_id, pinner in rows:
            counts[snapshot_id] = counts.get(snapshot_id, 0) + 1
            if pinner == user_id:
                mine.add(snapshot_id)
        return counts, mine

    @begin_session
    def set_pin(
        self,
        snapshot_id: int,
        user_id: int,
        pinned: bool,
        session: Session = INJECTED_SESSION,
    ) -> None:
        pin = session.get(SnapshotPin, (snapshot_id, user_id))
        if pinned and pin is None:
            session.add(SnapshotPin(snapshot_id=snapshot_id, user_id=user_id))
        elif not pinned and pin is not None:
            session.delete(pin)
        session.flush()

    @begin_session
    def drop_foreign_pins(
        self,
        owner_id: int,
        channel_id: uuid.UUID | None = None,
        snapshot_id: int | None = None,
        session: Session = INJECTED_SESSION,
    ) -> None:
        """Delete every pin but the owner's on a channel's snapshots, or on one
        snapshot, once other users can no longer read them."""
        held = (
            select(Snapshot.id).where(Snapshot.channel_id == channel_id)
            if channel_id is not None
            else select(Snapshot.id).where(Snapshot.id == snapshot_id)
        )
        session.execute(
            delete(SnapshotPin)
            .where(SnapshotPin.snapshot_id.in_(held), SnapshotPin.user_id != owner_id)
            .execution_options(synchronize_session=False)
        )

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
        return self.get_channel_files([channel], session=session).get(channel.id)

    @begin_session
    def get_channel_files(
        self, channels: Collection[Channel], session: Session = INJECTED_SESSION
    ) -> dict[uuid.UUID, RomFile]:
        """`get_channel_file` for each channel that has one, by channel id."""
        rom_ids = {c.rom_id for c in channels if c.rom_id is not None}
        if not rom_ids:
            return {}
        files_by_rom: dict[int, list[RomFile]] = {}
        for rom_file in session.scalars(
            select(RomFile).where(RomFile.rom_id.in_(rom_ids)).order_by(RomFile.id)
        ):
            files_by_rom.setdefault(rom_file.rom_id, []).append(rom_file)
        found: dict[uuid.UUID, RomFile] = {}
        for channel in channels:
            key = FileKey.of_channel(channel)
            match = next(
                (
                    rom_file
                    for rom_file in files_by_rom.get(channel.rom_id or -1, [])
                    if key.matches(FileKey.of_file(rom_file))
                ),
                None,
            )
            if match is not None:
                found[channel.id] = match
        return found

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
        for model, column, ids, public in (
            (Save, Save.id, save_ids, public_saves),
            (State, State.id, state_ids, public_states),
            (Screenshot, Screenshot.save_id, save_ids, public_saves),
            (Screenshot, Screenshot.state_id, state_ids, public_states),
        ):
            if ids:
                session.execute(
                    update(model)
                    .where(column.in_(ids))
                    .values(is_public=column.in_(public))
                    .execution_options(synchronize_session=False)
                )

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
        screenshots. A legacy upload the bridge made a current goes with its
        snapshot; a legacy row no snapshot holds is never taken."""
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
                ~_PINNED,
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
                ~_PINNED,
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
        """Delete a channel, keeping its current and the owner's pinned snapshots
        as archival. Legacy saves filed under it lose the link and become backups.
        A detached channel keeps nothing: with its ROM gone, no view could reach a
        backup."""
        channel = session.get_one(Channel, id, with_for_update=True)
        owner_pinned = exists().where(
            SnapshotPin.snapshot_id == Snapshot.id,
            SnapshotPin.user_id == channel.user_id,
        )
        kept = (
            session.scalars(
                select(Snapshot).where(
                    Snapshot.channel_id == id,
                    or_(Snapshot.id == channel.current_snapshot_id, owner_pinned),
                )
            ).all()
            if channel.rom_id is not None
            else []
        )
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
    def get_held_save_ids(
        self, save_ids: Collection[int], session: Session = INJECTED_SESSION
    ) -> set[int]:
        """Which of these saves a snapshot holds."""
        return held_save_ids(session, save_ids)

    @begin_session
    def is_frozen(
        self,
        save_id: int | None = None,
        state_id: int | None = None,
        session: Session = INJECTED_SESSION,
    ) -> bool:
        """Whether a channel or branch snapshot holds the row, so its bytes must not change."""
        if save_id is None:
            return bool(
                state_id is not None
                and self.get_frozen_state_ids([state_id], session=session)
            )
        query = select(Snapshot.id).where(
            Snapshot.kind.in_(_FREEZING_KINDS), Snapshot.save_id == save_id
        )
        return session.scalar(query.limit(1)) is not None

    @begin_session
    def get_frozen_state_ids(
        self, state_ids: Collection[int], session: Session = INJECTED_SESSION
    ) -> set[int]:
        """Which of these states a channel or branch snapshot holds."""
        if not state_ids:
            return set()
        return set(
            session.scalars(
                select(SnapshotState.state_id)
                .join(Snapshot, SnapshotState.snapshot_id == Snapshot.id)
                .where(
                    Snapshot.kind.in_(_FREEZING_KINDS),
                    SnapshotState.state_id.in_(state_ids),
                )
                .distinct()
            )
        )
