"""Paths that delete save and state rows leave the ones snapshots hold intact."""

from sqlalchemy import func, select
from tests.handler.snapshots.pushes import first_push

from handler.database import db_snapshot_handler, db_user_handler
from handler.database.base_handler import sync_session
from handler.streaming import states as streaming_states
from models.rom import Rom, RomFile
from models.snapshot import Snapshot
from models.user import User


async def test_deleting_a_user_takes_their_snapshots_and_content(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    await first_push(admin_user, rom, hashed_file)

    db_user_handler.delete_user(admin_user.id)

    with sync_session() as session:
        assert session.scalar(select(func.count()).select_from(Snapshot)) == 0


async def test_the_streaming_prune_leaves_a_state_a_snapshot_holds(
    admin_user: User, rom: Rom, hashed_file: RomFile, monkeypatch
):
    pushed = await first_push(admin_user, rom, hashed_file)
    [held] = (
        db_snapshot_handler.get_stored_content(pushed.snapshot)
        .states["snes9x"]
        .values()
    )
    monkeypatch.setattr(streaming_states, "STREAMING_STATE_HISTORY_LIMIT", 1)

    pruned = await streaming_states.prune_state_history(
        admin_user, rom, held.emulator or "", history=[held, held]
    )

    assert pruned == 0
    assert db_snapshot_handler.get_stored_content(pushed.snapshot).states
