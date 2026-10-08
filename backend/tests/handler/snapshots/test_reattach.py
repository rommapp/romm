from tests.factories import make_rom
from tests.handler.snapshots.pushes import first_push

from handler.database import db_rom_handler, db_snapshot_handler
from handler.database.base_handler import sync_session
from models.assets import Save
from models.platform import Platform
from models.rom import Rom, RomFile
from models.user import User


def scanned(rom_file: RomFile, sha1: str | None) -> RomFile:
    return RomFile(
        file_name=rom_file.file_name,
        file_path=rom_file.file_path,
        file_size_bytes=rom_file.file_size_bytes,
        sha1_hash=sha1,
    )


async def test_a_rescanned_file_reattaches_its_detached_channel(
    admin_user: User, rom: Rom, hashed_file: RomFile, platform: Platform
):
    result = await first_push(admin_user, rom, hashed_file)
    channel_id = result.snapshot.channel_id
    assert channel_id is not None
    db_rom_handler.delete_rom(rom.id)
    returned = make_rom(platform, "test_rom_again", slug="test_rom_again")

    db_rom_handler.sync_rom_files(
        returned.id, [scanned(hashed_file, hashed_file.sha1_hash)]
    )

    channel = db_snapshot_handler.get_channel(channel_id)
    snapshot = db_snapshot_handler.get_snapshot(result.snapshot.id)
    with sync_session() as session:
        save = session.get_one(Save, result.snapshot.save_id)
    assert channel is not None and channel.rom_id == returned.id
    assert snapshot is not None and snapshot.rom_id == returned.id
    assert save.rom_id == returned.id


async def test_a_rescanned_file_brings_back_an_archived_save_whose_game_was_removed(
    admin_user: User, rom: Rom, hashed_file: RomFile, platform: Platform
):
    result = await first_push(admin_user, rom, hashed_file)
    channel_id = result.snapshot.channel_id
    assert channel_id is not None
    db_snapshot_handler.delete_channel(channel_id)
    db_rom_handler.delete_rom(rom.id)
    returned = make_rom(platform, "test_rom_again", slug="test_rom_again")

    db_rom_handler.sync_rom_files(
        returned.id, [scanned(hashed_file, hashed_file.sha1_hash)]
    )

    snapshot = db_snapshot_handler.get_snapshot(result.snapshot.id)
    with sync_session() as session:
        save = session.get_one(Save, result.snapshot.save_id)
    assert snapshot is not None and snapshot.rom_id == returned.id
    assert snapshot.channel_id is None
    assert save.rom_id == returned.id


async def test_a_file_on_another_platform_leaves_the_channel_detached(
    admin_user: User,
    rom: Rom,
    hashed_file: RomFile,
    other_platform: Platform,
):
    result = await first_push(admin_user, rom, hashed_file)
    channel_id = result.snapshot.channel_id
    assert channel_id is not None
    db_rom_handler.delete_rom(rom.id)
    elsewhere = make_rom(other_platform, "same_bytes", slug="same_bytes")

    db_rom_handler.sync_rom_files(
        elsewhere.id, [scanned(hashed_file, hashed_file.sha1_hash)]
    )

    channel = db_snapshot_handler.get_channel(channel_id)
    assert channel is not None and channel.rom_id is None


async def test_hashing_a_file_rekeys_its_channels(
    admin_user: User, rom: Rom, rom_file: RomFile
):
    result = await first_push(admin_user, rom, rom_file)
    channel_id = result.snapshot.channel_id
    assert channel_id is not None
    before = db_snapshot_handler.get_channel(channel_id)
    assert before is not None and before.target_file_hash is None

    db_rom_handler.sync_rom_files(rom.id, [scanned(rom_file, "c" * 40)])

    after = db_snapshot_handler.get_channel(channel_id)
    assert after is not None and after.target_file_hash == "c" * 40
