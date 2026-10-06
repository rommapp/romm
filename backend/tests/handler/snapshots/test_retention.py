from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import update
from tests.handler.snapshots.pushes import first_push, push_save, stored_files

from handler.database import db_rom_handler, db_snapshot_handler
from handler.database.base_handler import sync_session
from handler.snapshots import retention
from handler.snapshots.write import WriteResult
from models.assets import Save, State
from models.rom import Rom, RomFile
from models.snapshot import Snapshot, SnapshotKind
from models.user import User

KEEP = 2


@pytest.fixture(autouse=True)
def _small_retention(monkeypatch):
    monkeypatch.setattr(retention, "SNAPSHOT_RETENTION", KEEP)


def alive(*results: WriteResult) -> list[bool]:
    return [
        db_snapshot_handler.get_snapshot(r.snapshot.id) is not None for r in results
    ]


async def five_pushes(user: User, rom: Rom, rom_file: RomFile) -> list[WriteResult]:
    results = [await first_push(user, rom, rom_file)]
    for n in range(4):
        results.append(
            await push_save(user, rom, rom_file, results[-1], f"save {n}".encode())
        )
    return results


async def test_a_push_keeps_the_channels_newest_snapshots(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    results = await five_pushes(admin_user, rom, hashed_file)

    assert alive(*results) == [False, False, False, True, True]


async def test_a_pinned_snapshot_stays_and_is_not_counted(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)
    db_snapshot_handler.update_snapshot(first.snapshot.id, {"is_pinned": True})
    results = [first]
    for n in range(4):
        results.append(
            await push_save(admin_user, rom, hashed_file, results[-1], f"s{n}".encode())
        )

    assert alive(*results) == [True, False, False, True, True]


async def test_pruning_removes_the_files_only_pruned_snapshots_held(
    admin_user: User, rom: Rom, hashed_file: RomFile, _assets_dir: Path
):
    results = await five_pushes(admin_user, rom, hashed_file)

    # The three oldest saves went; the state rides along in every kept bank.
    kept = {r.snapshot.save_id for r in results[-KEEP:]}
    with sync_session() as session:
        assert {save.id for save in session.query(Save)} == kept
        assert session.query(State).count() == 1
    # Two saves and one state on disk.
    assert len(stored_files(_assets_dir)) == 3


async def test_a_legacy_save_in_the_channel_survives_pruning(
    admin_user: User, rom: Rom, hashed_file: RomFile, save: Save
):
    results = await five_pushes(admin_user, rom, hashed_file)
    with sync_session.begin() as session:
        session.get_one(Save, save.id).channel_id = results[0].snapshot.channel_id

    await push_save(admin_user, rom, hashed_file, results[-1], b"one more")

    with sync_session() as session:
        assert session.get(Save, save.id) is not None


async def test_pruning_an_adopted_slot_upload_records_the_slots_loss(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    from handler.database import db_deleted_asset_handler

    first = await first_push(admin_user, rom, hashed_file)
    with sync_session.begin() as session:
        adopted = session.get_one(Save, first.snapshot.save_id)
        adopted.slot = "autosave"
        adopted_hash = adopted.content_hash
    results = [first]
    for n in range(3):
        results.append(
            await push_save(admin_user, rom, hashed_file, results[-1], f"a{n}".encode())
        )

    lost = db_deleted_asset_handler.removal_times(admin_user.id, rom.id, "autosave")

    assert alive(first) == [False]
    assert adopted_hash in lost


async def test_a_detached_channel_keeps_everything(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)
    channel_id = first.snapshot.channel_id
    assert channel_id is not None
    results = [first]
    for n in range(3):
        results.append(
            await push_save(admin_user, rom, hashed_file, results[-1], f"d{n}".encode())
        )
    survivors = [r for r, ok in zip(results, alive(*results), strict=True) if ok]
    db_rom_handler.delete_rom(rom.id)

    released = db_snapshot_handler.prune_channel(channel_id, keep=1)

    assert released.saves == [] and released.states == []
    assert all(alive(*survivors))


async def test_only_expired_branches_are_pruned(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)
    await push_save(admin_user, rom, hashed_file, first, b"current")
    old_branch = await push_save(admin_user, rom, hashed_file, first, b"stale")
    assert old_branch.snapshot.kind == SnapshotKind.BRANCH
    with sync_session.begin() as session:
        session.execute(
            update(Snapshot)
            .where(Snapshot.id == old_branch.snapshot.id)
            .values(
                created_at=datetime.now(timezone.utc)
                - retention.BRANCH_LIFETIME
                - timedelta(days=1)
            )
        )
    new_branch = await push_save(admin_user, rom, hashed_file, first, b"fresh")

    removed = await retention.prune_branches()

    assert removed == 1
    assert alive(old_branch, new_branch) == [False, True]


async def test_the_branch_lifetime_setting_moves_the_cutoff(
    admin_user: User, rom: Rom, hashed_file: RomFile, monkeypatch
):
    first = await first_push(admin_user, rom, hashed_file)
    await push_save(admin_user, rom, hashed_file, first, b"current")
    branch = await push_save(admin_user, rom, hashed_file, first, b"stale")
    with sync_session.begin() as session:
        session.execute(
            update(Snapshot)
            .where(Snapshot.id == branch.snapshot.id)
            .values(created_at=datetime.now(timezone.utc) - timedelta(days=3))
        )

    monkeypatch.setattr(retention, "BRANCH_LIFETIME", timedelta(days=7))
    await retention.prune_branches()
    kept = alive(branch)
    monkeypatch.setattr(retention, "BRANCH_LIFETIME", timedelta(days=2))
    await retention.prune_branches()

    assert kept == [True]
    assert alive(branch) == [False]


async def test_deleting_a_detached_channel_keeps_nothing_unreachable(
    admin_user: User, rom: Rom, hashed_file: RomFile, _assets_dir: Path
):
    results = await five_pushes(admin_user, rom, hashed_file)
    channel_id = results[0].snapshot.channel_id
    assert channel_id is not None
    db_snapshot_handler.update_snapshot(results[-2].snapshot.id, {"is_pinned": True})
    db_rom_handler.delete_rom(rom.id)

    await retention.discard_content(db_snapshot_handler.delete_channel(channel_id))

    with sync_session() as session:
        assert session.query(Snapshot).count() == 0
        assert session.query(Save).count() == 0
        assert session.query(State).count() == 0
    assert stored_files(_assets_dir) == []


async def test_deleting_a_channel_keeps_its_current_and_frees_its_legacy_saves(
    admin_user: User, rom: Rom, hashed_file: RomFile, save: Save
):
    results = await five_pushes(admin_user, rom, hashed_file)
    channel_id = results[0].snapshot.channel_id
    assert channel_id is not None
    with sync_session.begin() as session:
        session.get_one(Save, save.id).channel_id = channel_id

    await retention.discard_content(db_snapshot_handler.delete_channel(channel_id))

    current = db_snapshot_handler.get_snapshot(results[-1].snapshot.id)
    assert current is not None and current.kind == SnapshotKind.ARCHIVAL
    with sync_session() as session:
        remaining = {row.id: row.channel_id for row in session.query(Save)}
    assert remaining == {results[-1].snapshot.save_id: None, save.id: None}
