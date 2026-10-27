import pytest
from tests.factories import make_save

from handler.database import db_rom_handler, db_save_handler, db_snapshot_handler
from handler.snapshots.legacy import channel_label, may_load, sync_file
from models.assets import Save
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User


@pytest.mark.parametrize(
    "slot,label",
    [
        ("autosave", "default"),
        ("default", "default"),
        ("Default", "default"),
        ("Primary", "Primary"),
        ("Primary [2026-02-24_21-20-16]", "Primary"),
        ("Primary [2026-02-24_21-20-16-123]", "Primary"),
        ("state_1", None),
        (" [2026-02-24_21-20-16]", None),
    ],
)
def test_a_slot_names_its_channel(slot: str, label: str | None):
    assert channel_label(slot) == label


def _file(name: str, category: RomFileCategory | None = None) -> RomFile:
    return RomFile(file_name=name, file_path="p", file_size_bytes=1, category=category)


@pytest.mark.parametrize(
    "names,expected",
    [
        (["game.sfc"], "game.sfc"),
        (["Game (Track 2).bin", "Game (Track 1).bin", "Game.cue"], "Game.cue"),
        (["Game (Disc 2).chd", "Game (Disc 1).chd"], "Game (Disc 1).chd"),
    ],
)
def test_the_sync_file_is_the_one_an_emulator_loads(names: list[str], expected: str):
    chosen = sync_file([_file(name) for name in names])

    assert chosen is not None and chosen.file_name == expected


def test_the_sync_file_skips_a_manual():
    chosen = sync_file(
        [_file("a manual.pdf", RomFileCategory.MANUAL), _file("game.sfc")]
    )

    assert chosen is not None and chosen.file_name == "game.sfc"


@pytest.fixture
def game_file(rom: Rom) -> RomFile:
    return db_rom_handler.add_rom_file(
        RomFile(
            rom_id=rom.id,
            file_name="game.sfc",
            file_path=rom.fs_path,
            file_size_bytes=1024,
            sha1_hash="d" * 40,
        )
    )


def test_a_slotted_upload_files_under_the_slots_channel(
    rom: Rom, admin_user: User, game_file: RomFile
):
    first = make_save(rom, admin_user, "a.srm", slot="autosave")
    second = make_save(rom, admin_user, "b.srm", slot="autosave")
    tagged = make_save(rom, admin_user, "c.srm", slot="Run [2026-01-01_00-00-00]")
    retagged = make_save(rom, admin_user, "d.srm", slot="Run [2026-02-01_00-00-00]")
    backup = make_save(rom, admin_user, "e.srm", slot=None)

    assert first.channel_id is not None
    channel = db_snapshot_handler.get_channel(first.channel_id)
    assert channel is not None
    assert channel.label == "default"
    assert channel.target_file_hash == game_file.sha1_hash
    assert second.channel_id == first.channel_id
    assert tagged.channel_id is not None and tagged.channel_id != first.channel_id
    assert retagged.channel_id == tagged.channel_id
    assert backup.channel_id is None


def test_a_renamed_channel_keeps_its_slot(
    rom: Rom, admin_user: User, game_file: RomFile
):
    first = make_save(rom, admin_user, "a.srm", slot="autosave")
    assert first.channel_id is not None
    db_snapshot_handler.update_channel(first.channel_id, {"label": "Main run"})

    later = make_save(rom, admin_user, "b.srm", slot="autosave")

    assert later.channel_id == first.channel_id


def test_a_slot_spelled_in_another_case_shares_its_channel(
    rom: Rom, admin_user: User, game_file: RomFile
):
    first = make_save(rom, admin_user, "a.srm", slot="Second File")

    later = make_save(rom, admin_user, "b.srm", slot="second file")

    assert first.channel_id is not None
    assert later.channel_id == first.channel_id


def test_moving_a_save_out_of_its_slot_makes_it_a_backup(
    rom: Rom, admin_user: User, game_file: RomFile
):
    save = make_save(rom, admin_user, "a.srm", slot="autosave")

    moved = db_save_handler.update_save(save.id, {"slot": None})

    assert moved.channel_id is None


@pytest.mark.parametrize(
    "core,emulator,emulators,cores,loads",
    [
        ("mgba", "argosy", None, ["MGBA"], True),
        ("mgba", "argosy", None, ["gpsp"], False),
        ("mgba", "retroarch", ["retroarch"], ["gpsp"], False),
        ("mgba", "argosy", ["retroarch"], None, False),
        (None, "retroarch", ["RetroArch"], ["mgba"], True),
        (None, "retroarch", ["dolphin"], None, False),
        (None, None, ["retroarch"], ["mgba"], True),
        ("mgba", "argosy", None, None, True),
        ("mgba", "argosy", [None], [None], True),
    ],
)
def test_cores_decide_before_emulators_and_naming_nothing_loads(
    core: str | None,
    emulator: str | None,
    emulators: list[str | None] | None,
    cores: list[str | None] | None,
    loads: bool,
):
    save = Save(core=core, emulator=emulator)

    assert may_load(save, emulators, cores) is loads
