import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from handler.database.base_handler import sync_session
from models.assets import Save, Screenshot, State
from models.channel import DEFAULT_CHANNEL_LABEL, Channel
from models.rom import Rom
from models.snapshot import Snapshot, SnapshotKind, SnapshotState
from models.user import User

DIGEST = "0" * 64


def _channel(rom: Rom, user: User) -> Channel:
    return Channel(
        user_id=user.id,
        rom_id=rom.id,
        platform_id=rom.platform_id,
        target_file_name="game.sfc",
        target_file_size=1024,
        label=DEFAULT_CHANNEL_LABEL,
    )


def _snapshot(channel: Channel, **fields) -> Snapshot:
    return Snapshot(
        user_id=channel.user_id,
        rom_id=channel.rom_id,
        channel_id=channel.id,
        kind=SnapshotKind.CHANNEL,
        digest=DIGEST,
        **fields,
    )


def test_a_server_created_channel_gets_a_v7_id(rom: Rom, admin_user: User):
    with sync_session.begin() as session:
        channel = _channel(rom, admin_user)
        session.add(channel)

    assert channel.id.version == 7


def test_a_client_supplied_channel_id_is_kept(rom: Rom, admin_user: User):
    client_id = uuid.uuid4()
    with sync_session.begin() as session:
        channel = _channel(rom, admin_user)
        channel.id = client_id
        session.add(channel)

    with sync_session() as session:
        assert session.get(Channel, client_id) is not None


def test_a_channel_points_at_its_current_snapshot(rom: Rom, admin_user: User):
    with sync_session.begin() as session:
        channel = _channel(rom, admin_user)
        session.add(channel)
        session.flush()
        snapshot = _snapshot(channel)
        session.add(snapshot)
        session.flush()
        channel.current_snapshot_id = snapshot.id

    with sync_session() as session:
        stored = session.get_one(Channel, channel.id)
        assert stored.current_snapshot_id == snapshot.id


def test_deleting_a_channel_takes_its_snapshots_and_bank(
    rom: Rom, admin_user: User, state: State
):
    with sync_session.begin() as session:
        channel = _channel(rom, admin_user)
        session.add(channel)
        session.flush()
        snapshot = _snapshot(channel)
        snapshot.states = [SnapshotState(core="snes9x", slot="auto", state_id=state.id)]
        session.add(snapshot)
        session.flush()
        channel.current_snapshot_id = snapshot.id

    with sync_session.begin() as session:
        session.delete(session.get_one(Channel, channel.id))

    with sync_session() as session:
        assert session.get(Snapshot, snapshot.id) is None
        assert session.scalars(select(SnapshotState)).all() == []
        assert session.get(State, state.id) is not None


def test_pruning_a_parent_keeps_the_child(rom: Rom, admin_user: User):
    with sync_session.begin() as session:
        channel = _channel(rom, admin_user)
        session.add(channel)
        session.flush()
        parent = _snapshot(channel)
        session.add(parent)
        session.flush()
        child = _snapshot(channel, parent_snapshot_id=parent.id)
        session.add(child)

    with sync_session.begin() as session:
        session.delete(session.get_one(Snapshot, parent.id))

    with sync_session() as session:
        assert session.get_one(Snapshot, child.id).parent_snapshot_id is None


def test_a_save_a_snapshot_references_cannot_be_deleted(
    rom: Rom, admin_user: User, save: Save
):
    with sync_session.begin() as session:
        channel = _channel(rom, admin_user)
        session.add(channel)
        session.flush()
        session.add(_snapshot(channel, save_id=save.id))

    with pytest.raises(IntegrityError):
        with sync_session.begin() as session:
            session.delete(session.get_one(Save, save.id))


def test_a_state_a_bank_references_cannot_be_deleted(
    rom: Rom, admin_user: User, state: State
):
    with sync_session.begin() as session:
        channel = _channel(rom, admin_user)
        session.add(channel)
        session.flush()
        snapshot = _snapshot(channel)
        snapshot.states = [SnapshotState(core="snes9x", slot="3", state_id=state.id)]
        session.add(snapshot)

    with pytest.raises(IntegrityError):
        with sync_session.begin() as session:
            session.delete(session.get_one(State, state.id))


def test_deleting_a_save_takes_its_thumbnail(save: Save, screenshot: Screenshot):
    with sync_session.begin() as session:
        session.get_one(Screenshot, screenshot.id).save_id = save.id

    with sync_session.begin() as session:
        session.delete(session.get_one(Save, save.id))

    with sync_session() as session:
        assert session.get(Screenshot, screenshot.id) is None


def test_a_save_holds_one_thumbnail(
    save: Save, screenshot: Screenshot, rom: Rom, admin_user: User
):
    with sync_session.begin() as session:
        session.get_one(Screenshot, screenshot.id).save_id = save.id

    second = Screenshot(
        rom_id=rom.id,
        user_id=admin_user.id,
        file_name="second.png",
        file_path=screenshot.file_path,
        save_id=save.id,
    )
    with pytest.raises(IntegrityError):
        with sync_session.begin() as session:
            session.add(second)
