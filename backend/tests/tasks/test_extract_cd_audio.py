import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from rq.job import Job
from tests.handler.test_cd_audio import add_disc_rom, write_cue_disc

from handler import cd_audio
from handler.database import db_rom_handler
from handler.redis_handler import low_prio_queue
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from models.user import User
from tasks import extract_cd_audio as task_module
from tasks.extract_cd_audio import (
    extract_cd_audio_after_scan,
    queue_cd_audio_extraction,
)


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


async def test_encodes_nothing_for_a_fully_extracted_disc(
    admin_user: User,
    platform: Platform,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rom = _cue_rom(admin_user, platform, real_library, "Disc Game")
    await extract_cd_audio_after_scan([rom.id])
    encode = AsyncMock()
    monkeypatch.setattr(cd_audio, "encode_track", encode)

    await extract_cd_audio_after_scan([rom.id])

    encode.assert_not_awaited()


async def test_hands_the_rest_to_a_job_after_a_scan_that_starts(
    admin_user: User,
    platform: Platform,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _cue_rom(admin_user, platform, real_library, "First Game")
    second = _cue_rom(admin_user, platform, real_library, "Second Game")
    scan = MagicMock(spec=Job)
    scans = iter([None, scan])
    monkeypatch.setattr(task_module, "get_running_scan_job", lambda: next(scans))
    enqueue = MagicMock()
    monkeypatch.setattr(low_prio_queue, "enqueue", enqueue)

    await extract_cd_audio_after_scan([first.id, second.id])

    assert _soundtrack(first.id) == ["Disc - Track 02.flac", "Disc - Track 03.flac"]
    assert _soundtrack(second.id) == []
    assert enqueue.call_args.kwargs["kwargs"] == {"rom_ids": [second.id]}
    dependency = enqueue.call_args.kwargs["depends_on"]
    assert dependency.dependencies == [scan]
    assert dependency.allow_failure is True


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


@pytest.mark.parametrize(
    "error",
    [
        cd_audio.CdAudioEncodeException("unreadable"),
        cd_audio.CdAudioNeedsFolderException("loose sheet"),
    ],
)
async def test_a_disc_it_cannot_extract_does_not_stop_the_rest(
    admin_user: User,
    platform: Platform,
    real_library: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    broken = _cue_rom(admin_user, platform, real_library, "Broken Game")
    working = _cue_rom(admin_user, platform, real_library, "Working Game")

    async def fail_on_broken(rom: Rom) -> cd_audio.CdAudioExtraction:
        if rom.id == broken.id:
            raise error
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

    def test_queues_those_of_the_roms_with_a_disc_image(
        self, platform: Platform, enqueue: MagicMock
    ) -> None:
        cue = _add_rom(platform, "cue", [_game_file("Disc.cue")])
        chd = _add_rom(platform, "chd", [_game_file("DISC.CHD")])
        iso = _add_rom(platform, "iso", [_game_file("disc.iso")])
        # A sheet among the soundtrack files isn't a disc of the game.
        extra = _add_rom(
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
        gone = _add_rom(
            platform, "gone", [_game_file("gone.gdi", missing_from_fs=True)]
        )
        unlisted = _add_rom(platform, "unlisted", [_game_file("unlisted.gdi")])

        queue_cd_audio_extraction([cue.id, chd.id, iso.id, extra.id, gone.id])

        enqueue.assert_called_once()
        assert enqueue.call_args.args == (extract_cd_audio_after_scan,)
        assert enqueue.call_args.kwargs["kwargs"] == {"rom_ids": [cue.id, chd.id]}
        assert unlisted.id not in enqueue.call_args.kwargs["kwargs"]["rom_ids"]
        assert enqueue.call_args.kwargs["depends_on"] is None

    def test_waits_for_the_scan_job_that_queues_it(
        self,
        platform: Platform,
        enqueue: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cue = _add_rom(platform, "cue", [_game_file("Disc.cue")])
        scan_job = MagicMock(spec=Job)
        monkeypatch.setattr(task_module, "get_current_job", lambda: scan_job)

        queue_cd_audio_extraction([cue.id])

        dependency = enqueue.call_args.kwargs["depends_on"]
        assert dependency.dependencies == [scan_job]
        assert dependency.allow_failure is True

    def test_queues_nothing_without_a_disc_image(
        self, platform: Platform, enqueue: MagicMock
    ) -> None:
        iso = _add_rom(platform, "iso", [_game_file("disc.iso")])

        assert queue_cd_audio_extraction([iso.id]) is None
        assert queue_cd_audio_extraction([]) is None
        enqueue.assert_not_called()
