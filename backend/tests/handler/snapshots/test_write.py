import io
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import UploadFile as StarletteUploadFile
from sqlalchemy import select, update
from tests._zipfile_shim import reload_zipfile
from tests.handler.snapshots.pushes import (
    SRAM,
    STATE_A,
    STATE_B,
    count,
    first_push,
    md5,
    part,
    push,
    push_save,
    save_entry,
    stored_bytes,
    stored_files,
)

from handler.database import db_snapshot_handler
from handler.database.base_handler import sync_session
from handler.filesystem.assets_handler import hash_zip_contents
from handler.snapshots import write as write_module
from handler.snapshots.manifest import Manifest, SaveEntry
from handler.snapshots.write import (
    SAVE_PART,
    ContentMismatch,
    ContentMissing,
    FileMismatch,
    HardcoreDowngrade,
    LabelRequired,
    NotVisible,
    Outcome,
    SnapshotWrite,
    UploadPart,
    WriteResult,
    state_part,
    write_snapshot,
)
from models.assets import Save, SaveFormat, SaveShape, Screenshot, State
from models.channel import Channel
from models.device import Device
from models.device_channel_sync import DeviceChannelSync
from models.rom import Rom, RomFile
from models.snapshot import SnapshotKind
from models.user import User
from utils.datetime import to_utc


async def test_the_first_push_creates_the_channel_and_points_it_at_the_snapshot(
    admin_user: User, rom: Rom, hashed_file: RomFile, device: Device
):
    result = await first_push(admin_user, rom, hashed_file, device_id=device.id)

    assert result.outcome == Outcome.CREATED
    snapshot = result.snapshot
    assert snapshot.kind == SnapshotKind.CHANNEL
    assert snapshot.channel_id is not None
    channel = db_snapshot_handler.get_channel(snapshot.channel_id)
    assert channel is not None
    assert channel.current_snapshot_id == snapshot.id
    assert channel.label == "default"
    assert channel.target_file_hash == hashed_file.sha1_hash
    assert snapshot.rom_sha1 == hashed_file.sha1_hash
    with sync_session() as session:
        save = session.get_one(Save, snapshot.save_id)
        sync = session.get_one(DeviceChannelSync, (device.id, channel.id))
    assert save.content_hash == md5(SRAM)
    assert save.identity_hash == md5(SRAM)
    assert save.shape == SaveShape.SINGLE
    assert save.format == SaveFormat.NEUTRAL
    assert stored_bytes(save.full_path) == SRAM
    assert sync.base_snapshot_id == snapshot.id


async def test_a_client_supplied_channel_id_creates_that_channel(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    client_id = uuid.uuid4()

    result = await first_push(admin_user, rom, hashed_file)
    offline = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(),
            expected=None,
            channel_id=client_id,
            label="Speedrun",
            parent_snapshot_id=result.snapshot.id,
        )
    )

    assert offline.snapshot.channel_id == client_id
    assert offline.snapshot.save_id == result.snapshot.save_id
    assert offline.snapshot.parent_snapshot_id == result.snapshot.id


async def test_a_new_channel_needs_a_label(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    with pytest.raises(LabelRequired):
        await write_snapshot(
            push(admin_user, rom, hashed_file, Manifest(save=None), None, label=None)
        )


async def test_an_omitted_core_carries_and_a_listed_core_replaces(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(
                states={
                    "snes9x": {"auto": md5(STATE_A), "3": md5(STATE_B)},
                    "bsnes": {"auto": md5(STATE_A)},
                }
            ),
            expected=None,
            parts={
                state_part("snes9x", "auto"): part(STATE_A, "a.state"),
                state_part("snes9x", "3"): part(STATE_B, "b.state"),
            },
        )
    )
    channel_id = first.snapshot.channel_id

    second = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(states={"snes9x": {"auto": md5(STATE_B)}}),
            expected=first.snapshot.id,
            channel_id=channel_id,
        )
    )
    third = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(states={"bsnes": {}}),
            expected=second.snapshot.id,
            channel_id=channel_id,
        )
    )

    resolved = db_snapshot_handler.get_stored_content(second.snapshot).resolved()
    assert resolved.bank == {
        "snes9x": {"auto": md5(STATE_B)},
        "bsnes": {"auto": md5(STATE_A)},
    }
    after_empty = db_snapshot_handler.get_stored_content(third.snapshot).resolved()
    assert after_empty.bank == {"snes9x": {"auto": md5(STATE_B)}}
    assert count(State) == 2


async def test_a_stale_push_is_kept_as_a_branch(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)
    channel_id = first.snapshot.channel_id
    newer = b"newer"
    second = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry(newer)),
            expected=first.snapshot.id,
            channel_id=channel_id,
            parts={SAVE_PART: part(newer)},
        )
    )
    other = b"other device"

    stale = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry(other)),
            expected=first.snapshot.id,
            channel_id=channel_id,
            parts={SAVE_PART: part(other)},
        )
    )

    assert stale.outcome == Outcome.BRANCHED
    assert stale.snapshot.kind == SnapshotKind.BRANCH
    assert stale.current is not None and stale.current.id == second.snapshot.id
    assert channel_id is not None
    channel = db_snapshot_handler.get_channel(channel_id)
    assert channel is not None and channel.current_snapshot_id == second.snapshot.id


async def test_pushing_the_current_content_again_writes_nothing(
    admin_user: User, rom: Rom, hashed_file: RomFile, _assets_dir: Path
):
    first = await first_push(admin_user, rom, hashed_file)
    files_before = stored_files(_assets_dir)

    again = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry(), states={"snes9x": {"auto": md5(STATE_A)}}),
            expected=None,
            channel_id=first.snapshot.channel_id,
            parts={SAVE_PART: part(SRAM)},
        )
    )

    assert again.outcome == Outcome.UNCHANGED
    assert again.snapshot.id == first.snapshot.id
    assert stored_files(_assets_dir) == files_before


async def test_hashing_a_parents_unhashed_save_keeps_its_updated_at(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)
    save_id = first.snapshot.save_id
    stamp = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with sync_session.begin() as session:
        session.execute(
            update(Save)
            .where(Save.id == save_id)
            .values(content_hash=None, updated_at=stamp)
        )

    result = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(states={"snes9x": {"auto": md5(STATE_B)}}),
            expected=first.snapshot.id,
            channel_id=first.snapshot.channel_id,
            parts={state_part("snes9x", "auto"): part(STATE_B, "game.state")},
        )
    )

    with sync_session() as session:
        save = session.get_one(Save, save_id)
    assert result.outcome == Outcome.CREATED
    assert result.snapshot.save_id == save_id
    assert save.content_hash == md5(SRAM)
    assert to_utc(save.updated_at) == stamp


async def test_unknown_content_without_a_part_is_reported_and_nothing_is_stored(
    admin_user: User, rom: Rom, hashed_file: RomFile, _assets_dir: Path
):
    with pytest.raises(ContentMissing) as missing:
        await write_snapshot(
            push(
                admin_user,
                rom,
                hashed_file,
                Manifest(save=save_entry(), states={"snes9x": {"3": md5(STATE_B)}}),
                expected=None,
            )
        )

    assert missing.value.keys == ["save", "state:snes9x:3"]
    assert stored_files(_assets_dir) == []
    assert count(Channel) == 0


async def test_a_part_that_does_not_match_its_hash_is_refused_and_removed(
    admin_user: User, rom: Rom, hashed_file: RomFile, _assets_dir: Path
):
    with pytest.raises(ContentMismatch):
        await write_snapshot(
            push(
                admin_user,
                rom,
                hashed_file,
                Manifest(save=save_entry()),
                expected=None,
                parts={SAVE_PART: part(b"something else")},
            )
        )

    assert stored_files(_assets_dir) == []
    assert count(Save) == 0


@pytest.mark.parametrize(
    "approve,outcome",
    [(False, None), (True, Outcome.CREATED)],
    ids=["refused", "approved"],
)
async def test_a_softcore_save_over_a_hardcore_current_needs_approval(
    admin_user: User, rom: Rom, hashed_file: RomFile, approve: bool, outcome
):
    first = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry(), is_hardcore=True),
            expected=None,
            parts={SAVE_PART: part(SRAM)},
        )
    )
    softcore = b"softcore"
    write = push(
        admin_user,
        rom,
        hashed_file,
        Manifest(save=save_entry(softcore), approve_hardcore_downgrade=approve),
        expected=first.snapshot.id,
        channel_id=first.snapshot.channel_id,
        parts={SAVE_PART: part(softcore)},
    )

    channel_id = first.snapshot.channel_id
    assert channel_id is not None
    if outcome is None:
        with pytest.raises(HardcoreDowngrade):
            await write_snapshot(write)
        channel = db_snapshot_handler.get_channel(channel_id)
        assert channel is not None and channel.is_hardcore
        return

    result = await write_snapshot(write)
    assert result.outcome == outcome
    channel = db_snapshot_handler.get_channel(channel_id)
    assert channel is not None and not channel.is_hardcore
    older = db_snapshot_handler.get_snapshot(first.snapshot.id)
    assert older is not None and older.is_hardcore


async def test_a_hardcore_snapshot_holds_no_states(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)

    hardcore = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(is_hardcore=True),
            expected=first.snapshot.id,
            channel_id=first.snapshot.channel_id,
        )
    )

    assert db_snapshot_handler.get_stored_content(hardcore.snapshot).states == {}


async def test_a_private_channel_is_hidden_from_other_users(
    admin_user: User, editor_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)

    with pytest.raises(NotVisible):
        await write_snapshot(
            push(
                editor_user,
                rom,
                hashed_file,
                Manifest(),
                expected=first.snapshot.id,
                channel_id=first.snapshot.channel_id,
            )
        )


async def test_another_user_pushes_into_a_public_channel_as_its_author(
    admin_user: User, editor_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)
    with sync_session.begin() as session:
        session.get_one(Channel, first.snapshot.channel_id).is_public = True
    theirs = b"theirs"

    result = await write_snapshot(
        push(
            editor_user,
            rom,
            hashed_file,
            Manifest(save=save_entry(theirs)),
            expected=first.snapshot.id,
            channel_id=first.snapshot.channel_id,
            parts={SAVE_PART: part(theirs)},
        )
    )

    assert result.outcome == Outcome.CREATED
    assert result.snapshot.user_id == admin_user.id
    assert result.snapshot.author_user_id == editor_user.id
    with sync_session() as session:
        assert session.get_one(Save, result.snapshot.save_id).user_id == admin_user.id


async def test_a_push_from_another_file_is_refused(
    admin_user: User, rom: Rom, hashed_file: RomFile, rom_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)

    with pytest.raises(FileMismatch):
        await write_snapshot(
            push(
                admin_user,
                rom,
                rom_file,
                Manifest(),
                expected=first.snapshot.id,
                channel_id=first.snapshot.channel_id,
            )
        )


async def test_an_archival_write_moves_no_pointer(admin_user: User, rom: Rom):
    result = await write_snapshot(
        SnapshotWrite(
            author=admin_user,
            rom=rom,
            manifest=Manifest(save=save_entry(fmt=SaveFormat.NATIVE)),
            channel=None,
            parts={SAVE_PART: part(SRAM)},
            is_public=True,
        )
    )

    assert result.snapshot.kind == SnapshotKind.ARCHIVAL
    assert result.snapshot.channel_id is None
    assert result.snapshot.is_public
    assert count(Channel) == 0


async def test_the_same_bytes_in_another_channel_reuse_one_row(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)

    second = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry()),
            expected=None,
            label="Second run",
            parts={SAVE_PART: part(SRAM)},
        )
    )

    assert second.snapshot.channel_id != first.snapshot.channel_id
    assert second.snapshot.save_id == first.snapshot.save_id
    assert count(Save) == 1


async def test_a_pushed_row_is_filed_under_its_channel(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    result = await first_push(admin_user, rom, hashed_file)

    with sync_session() as session:
        save = session.get_one(Save, result.snapshot.save_id)
        state = session.scalars(select(State)).one()
    assert save.channel_id == result.snapshot.channel_id
    assert state.channel_id == result.snapshot.channel_id


async def test_a_legacy_row_with_the_same_bytes_is_never_adopted(
    admin_user: User, rom: Rom, hashed_file: RomFile, save: Save
):
    with sync_session.begin() as session:
        session.get_one(Save, save.id).content_hash = md5(SRAM)

    with pytest.raises(ContentMissing):
        await write_snapshot(
            push(
                admin_user, rom, hashed_file, Manifest(save=save_entry()), expected=None
            )
        )
    result = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry()),
            expected=None,
            parts={SAVE_PART: part(SRAM)},
        )
    )

    assert result.snapshot.save_id != save.id


async def test_a_neutral_identity_hash_leaves_out_the_clock(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("save.sram", SRAM)
        zf.writestr("clock.rtc", b"tick")
    archive = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        content_hash = hash_zip_contents(zf)

    result = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(
                save=SaveEntry(
                    hash=content_hash, shape=SaveShape.MULTI, format=SaveFormat.NEUTRAL
                )
            ),
            expected=None,
            parts={SAVE_PART: part(archive, "save.sram.zip")},
        )
    )

    with sync_session() as session:
        save = session.get_one(Save, result.snapshot.save_id)
    assert save.content_hash == content_hash
    assert save.identity_hash == md5(SRAM)


async def test_a_screenshot_for_stored_content_attaches_only_where_none_exists(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)

    def repeat(shot: bytes) -> SnapshotWrite:
        return push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry(), states={"snes9x": {"auto": md5(STATE_A)}}),
            expected=first.snapshot.id,
            channel_id=first.snapshot.channel_id,
            parts={
                SAVE_PART: UploadPart(
                    content=SRAM,
                    file_name="game.srm",
                    screenshot=shot,
                    screenshot_name="s.png",
                ),
                state_part("snes9x", "auto"): UploadPart(
                    content=STATE_A,
                    file_name="game.state",
                    screenshot=shot,
                    screenshot_name="a.png",
                ),
            },
        )

    first_repeat = await write_snapshot(repeat(b"first shot"))
    second_repeat = await write_snapshot(repeat(b"second shot"))

    content = db_snapshot_handler.get_stored_content(first.snapshot)
    assert content.save is not None
    [state] = content.states["snes9x"].values()
    save_shots, state_shots = db_snapshot_handler.get_thumbnails(
        [content.save.id], [state.id]
    )
    assert first_repeat.outcome == second_repeat.outcome == Outcome.UNCHANGED
    assert stored_bytes(save_shots[content.save.id].full_path) == b"first shot"
    assert stored_bytes(state_shots[state.id].full_path) == b"first shot"


def neutral_unit(
    sram: bytes,
    clock: bytes,
    names: tuple[str, str] = ("save.sram", "clock.rtc"),
    fmt: SaveFormat = SaveFormat.NEUTRAL,
) -> tuple[bytes, SaveEntry]:
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(names[0], sram)
        zf.writestr(names[1], clock)
    archive = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        content_hash = hash_zip_contents(zf)
    entry = SaveEntry(hash=content_hash, shape=SaveShape.MULTI, format=fmt)
    return archive, entry


async def test_a_native_clock_only_change_is_no_new_snapshot(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    names = ("game.srm", "game.rtc")
    archive, entry = neutral_unit(SRAM, b"tick", names, SaveFormat.NATIVE)
    first = await push_unit(admin_user, rom, hashed_file, archive, entry, None)
    archive, entry = neutral_unit(SRAM, b"tock", names, SaveFormat.NATIVE)

    result = await push_unit(
        admin_user,
        rom,
        hashed_file,
        archive,
        entry,
        first.snapshot.id,
        first.snapshot.channel_id,
    )

    assert result.outcome == Outcome.UNCHANGED


async def push_unit(
    user: User,
    rom: Rom,
    rom_file: RomFile,
    archive: bytes,
    entry: SaveEntry,
    expected: int | None,
    channel_id: uuid.UUID | None = None,
    states: dict[str, dict[str, str]] | None = None,
) -> WriteResult:
    state_parts = (
        {state_part("snes9x", "auto"): part(STATE_A, "game.state")} if states else {}
    )
    return await write_snapshot(
        push(
            user,
            rom,
            rom_file,
            Manifest(save=entry, states=states or {}),
            expected=expected,
            channel_id=channel_id,
            parts={SAVE_PART: part(archive, "save.sram.zip"), **state_parts},
        )
    )


@pytest.mark.parametrize(
    "sram,states,outcome",
    [
        (SRAM, None, Outcome.UNCHANGED),
        (b"more-progress", None, Outcome.CREATED),
        (SRAM, {"snes9x": {"auto": md5(STATE_A)}}, Outcome.CREATED),
    ],
)
async def test_a_clock_only_change_is_no_new_snapshot(
    admin_user: User,
    rom: Rom,
    hashed_file: RomFile,
    _assets_dir: Path,
    sram: bytes,
    states: dict[str, dict[str, str]] | None,
    outcome: Outcome,
):
    first_archive, first_entry = neutral_unit(SRAM, b"tick")
    first = await push_unit(
        admin_user, rom, hashed_file, first_archive, first_entry, None
    )
    files_before = stored_files(_assets_dir)
    archive, entry = neutral_unit(sram, b"tock")

    result = await push_unit(
        admin_user,
        rom,
        hashed_file,
        archive,
        entry,
        first.snapshot.id,
        first.snapshot.channel_id,
        states,
    )

    assert result.outcome == outcome
    if outcome == Outcome.UNCHANGED:
        assert result.snapshot.id == first.snapshot.id
        assert stored_files(_assets_dir) == files_before


async def test_checking_for_a_clock_only_change_leaves_an_upload_readable(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first_archive, first_entry = neutral_unit(SRAM, b"tick")
    first = await push_unit(
        admin_user, rom, hashed_file, first_archive, first_entry, None
    )
    archive, entry = neutral_unit(b"more-progress", b"tock")
    upload = StarletteUploadFile(file=io.BytesIO(archive), filename="save.sram.zip")

    result = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=entry),
            expected=first.snapshot.id,
            channel_id=first.snapshot.channel_id,
            parts={SAVE_PART: UploadPart(content=upload, file_name="save.sram.zip")},
        )
    )

    with sync_session() as session:
        save = session.get_one(Save, result.snapshot.save_id)
    assert stored_bytes(save.full_path) == archive


async def test_a_native_save_whose_bytes_change_is_a_new_snapshot(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    first = await first_push(admin_user, rom, hashed_file)

    result = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry(b"native tick", SaveFormat.NATIVE)),
            expected=first.snapshot.id,
            channel_id=first.snapshot.channel_id,
            parts={SAVE_PART: part(b"native tick")},
        )
    )

    assert result.outcome == Outcome.CREATED


async def test_a_repeat_whose_current_moves_before_commit_is_planned_again(
    admin_user: User, rom: Rom, hashed_file: RomFile, monkeypatch
):
    first = await first_push(admin_user, rom, hashed_file)
    planned = write_module._plan
    moved: list[WriteResult] = []
    racing: list[bool] = []

    async def plan_then_move(write: SnapshotWrite, match_current: bool = True):
        plan = await planned(write, match_current)
        if not racing:
            racing.append(True)
            moved.append(await push_save(admin_user, rom, hashed_file, first, b"race"))
        return plan

    monkeypatch.setattr(write_module, "_plan", plan_then_move)

    repeat = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry(), states={"snes9x": {"auto": md5(STATE_A)}}),
            expected=first.snapshot.id,
            channel_id=first.snapshot.channel_id,
            parts={SAVE_PART: part(SRAM)},
        )
    )

    [winner] = moved
    assert repeat.outcome == Outcome.BRANCHED
    assert repeat.current is not None and repeat.current.id == winner.snapshot.id


async def test_a_screenshot_part_is_linked_to_its_row(
    admin_user: User, rom: Rom, hashed_file: RomFile
):
    result = await write_snapshot(
        push(
            admin_user,
            rom,
            hashed_file,
            Manifest(save=save_entry()),
            expected=None,
            parts={
                SAVE_PART: UploadPart(
                    content=SRAM,
                    file_name="game.srm",
                    screenshot=b"png",
                    screenshot_name="shot.png",
                )
            },
        )
    )

    with sync_session() as session:
        shot = session.scalar(
            select(Screenshot).where(Screenshot.save_id == result.snapshot.save_id)
        )
    assert shot is not None
    assert shot.file_name.endswith(".png")
