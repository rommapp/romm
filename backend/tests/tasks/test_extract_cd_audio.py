import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from tests.endpoints.roms.test_cd_audio import add_disc_rom, write_cue_disc

from endpoints.responses.rom import CdAudioExtractionSchema
from handler import cd_audio
from handler.database import db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.redis_handler import low_prio_queue
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User
from tasks import extract_cd_audio as task_module
from tasks.extract_cd_audio import (
    extract_cd_audio_after_scan,
    queue_cd_audio_extraction,
)


@pytest.fixture
def real_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()
    monkeypatch.setattr(fs_rom_handler, "base_path", lib.resolve())
    return lib


@pytest.fixture(autouse=True)
def no_running_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(task_module, "get_running_scan_job", lambda: None)


def _cue_rom(
    admin_user: User, platform: Platform, real_library: Path, name: str
) -> Rom:
    fs_path = f"{platform.slug}/roms/{name}"
    contents = write_cue_disc(real_library / fs_path)
    return add_disc_rom(
        admin_user,
        platform,
        name,
        {file_name: len(data) for file_name, data in contents.items()},
        fs_path,
    )


def _soundtrack(rom_id: int) -> list[str]:
    rom = db_rom_handler.get_rom(rom_id)
    assert rom is not None
    return sorted(
        f.file_name for f in rom.files if f.category == RomFileCategory.SOUNDTRACK
    )


async def test_extracts_the_missing_tracks(
    admin_user: User, platform: Platform, real_library: Path
) -> None:
    rom = _cue_rom(admin_user, platform, real_library, "Disc Game")

    await extract_cd_audio_after_scan([rom.id])

    assert _soundtrack(rom.id) == ["Disc - Track 02.flac", "Disc - Track 03.flac"]


async def test_leaves_a_fully_extracted_disc_alone(
    admin_user: User,
    platform: Platform,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rom = _cue_rom(admin_user, platform, real_library, "Disc Game")
    await extract_cd_audio_after_scan([rom.id])
    extract = MagicMock()
    monkeypatch.setattr(task_module, "extract_cd_audio", extract)

    await extract_cd_audio_after_scan([rom.id])

    extract.assert_not_called()


async def test_stops_when_a_scan_starts(
    admin_user: User,
    platform: Platform,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rom = _cue_rom(admin_user, platform, real_library, "Disc Game")
    monkeypatch.setattr(task_module, "get_running_scan_job", lambda: MagicMock())

    await extract_cd_audio_after_scan([rom.id])

    assert _soundtrack(rom.id) == []


async def test_does_nothing_without_the_encoder(
    admin_user: User,
    platform: Platform,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rom = _cue_rom(admin_user, platform, real_library, "Disc Game")
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    await extract_cd_audio_after_scan([rom.id])

    assert _soundtrack(rom.id) == []


async def test_a_failing_disc_does_not_stop_the_rest(
    admin_user: User,
    platform: Platform,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = _cue_rom(admin_user, platform, real_library, "Broken Game")
    working = _cue_rom(admin_user, platform, real_library, "Working Game")

    async def fail_on_broken(rom: Rom) -> CdAudioExtractionSchema:
        if rom.id == broken.id:
            raise cd_audio.CdAudioEncodeException("unreadable")
        return await cd_audio.extract_cd_audio(rom)

    monkeypatch.setattr(task_module, "extract_cd_audio", fail_on_broken)

    await extract_cd_audio_after_scan([broken.id, working.id])

    assert _soundtrack(broken.id) == []
    assert _soundtrack(working.id) == [
        "Disc - Track 02.flac",
        "Disc - Track 03.flac",
    ]


def _add_rom(platform: Platform, fs_name: str, files: list[RomFile]) -> Rom:
    rom = db_rom_handler.add_rom(
        Rom(
            platform_id=platform.id,
            name=fs_name,
            slug=fs_name,
            fs_name=fs_name,
            fs_name_no_tags=fs_name,
            fs_name_no_ext=fs_name,
            fs_extension="",
            fs_path=f"{platform.slug}/roms",
        )
    )
    for file in files:
        file.rom_id = rom.id
        file.file_path = f"{platform.slug}/roms/{fs_name}"
        db_rom_handler.add_rom_file(file)
    return rom


def _game_file(name: str, **kwargs: object) -> RomFile:
    return RomFile(
        file_name=name, file_size_bytes=1, category=RomFileCategory.GAME, **kwargs
    )


class TestQueueing:
    @pytest.fixture
    def enqueue(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        enqueue = MagicMock()
        monkeypatch.setattr(low_prio_queue, "enqueue", enqueue)
        return enqueue

    def test_queues_the_roms_with_a_disc_image(
        self, platform: Platform, other_platform: Platform, enqueue: MagicMock
    ) -> None:
        cue = _add_rom(platform, "cue", [_game_file("Disc.cue")])
        chd = _add_rom(platform, "chd", [_game_file("DISC.CHD")])
        _add_rom(platform, "iso", [_game_file("disc.iso")])
        # A sheet among the soundtrack files isn't a disc of the game.
        _add_rom(
            platform,
            "extra",
            [
                _game_file("game.bin"),
                RomFile(
                    file_name="bonus.cue",
                    file_size_bytes=1,
                    category=RomFileCategory.SOUNDTRACK,
                ),
            ],
        )
        _add_rom(platform, "gone", [_game_file("gone.gdi", missing_from_fs=True)])
        _add_rom(other_platform, "elsewhere", [_game_file("elsewhere.gdi")])

        queue_cd_audio_extraction(platform_ids=[platform.id])

        enqueue.assert_called_once()
        assert enqueue.call_args.args == (extract_cd_audio_after_scan,)
        assert enqueue.call_args.kwargs["kwargs"] == {"rom_ids": [cue.id, chd.id]}
        assert enqueue.call_args.kwargs["depends_on"] is None

    def test_waits_for_the_scan_job_that_queues_it(
        self,
        platform: Platform,
        enqueue: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _add_rom(platform, "cue", [_game_file("Disc.cue")])
        scan_job = MagicMock()
        monkeypatch.setattr(task_module, "get_current_job", lambda: scan_job)

        queue_cd_audio_extraction(platform_ids=[platform.id])

        assert enqueue.call_args.kwargs["depends_on"] is scan_job

    def test_named_roms_narrow_the_platforms(
        self, platform: Platform, enqueue: MagicMock
    ) -> None:
        _add_rom(platform, "one", [_game_file("one.cue")])
        two = _add_rom(platform, "two", [_game_file("two.cue")])

        queue_cd_audio_extraction(platform_ids=[platform.id], rom_ids=[two.id])

        assert enqueue.call_args.kwargs["kwargs"] == {"rom_ids": [two.id]}

    def test_queues_nothing_without_a_disc_image(
        self, platform: Platform, enqueue: MagicMock
    ) -> None:
        _add_rom(platform, "iso", [_game_file("disc.iso")])

        assert queue_cd_audio_extraction(platform_ids=[platform.id]) is None
        enqueue.assert_not_called()
