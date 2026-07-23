from unittest.mock import Mock

import handler.scan_handler as scan_handler
from handler.scan_handler import persist_soundtrack_cover
from models.rom import Rom, RomFile, RomFileCategory, TrackMeta


def _rom() -> Rom:
    rom = Rom(platform_id=1)
    rom.id = 7
    return rom


def _soundtrack_file(*, has_cover: bool, cover_path: str | None) -> RomFile:
    rom_file = RomFile(
        rom_id=7,
        file_name="track01.flac",
        file_path="test/roms/game/soundtrack",
        category=RomFileCategory.SOUNDTRACK,
        track_meta=TrackMeta(
            rom_id=7, has_embedded_cover=has_cover, cover_path=cover_path
        ),
    )
    rom_file.id = 21
    return rom_file


class TestPersistSoundtrackCoverRemoval:
    """A rescan reuses the file row, so a cover stripped from the audio file
    since the last scan must be cleared instead of being served forever from a
    now-orphaned resource."""

    def test_lost_cover_is_removed_and_cleared(self, mocker):
        remove = mocker.patch.object(scan_handler, "remove_persisted_cover")
        db = mocker.patch.object(scan_handler, "db_rom_handler")

        persist_soundtrack_cover(
            _soundtrack_file(has_cover=False, cover_path="covers/track01.png"), _rom()
        )

        remove.assert_called_once_with("covers/track01.png")
        db.upsert_track_meta.assert_called_once_with(21, 7, {"cover_path": None})

    def test_no_cover_and_no_path_is_a_noop(self, mocker):
        remove = mocker.patch.object(scan_handler, "remove_persisted_cover")
        db = mocker.patch.object(scan_handler, "db_rom_handler")

        persist_soundtrack_cover(
            _soundtrack_file(has_cover=False, cover_path=None), _rom()
        )

        remove.assert_not_called()
        db.upsert_track_meta.assert_not_called()

    def test_existing_cover_is_repersisted(self, mocker):
        remove = mocker.patch.object(scan_handler, "remove_persisted_cover")
        db = mocker.patch.object(scan_handler, "db_rom_handler")
        mocker.patch.object(
            scan_handler.fs_rom_handler, "validate_path", Mock(return_value="/audio")
        )
        mocker.patch.object(
            scan_handler,
            "persist_embedded_cover",
            Mock(return_value="covers/track01.png"),
        )

        persist_soundtrack_cover(
            _soundtrack_file(has_cover=True, cover_path="covers/track01.png"), _rom()
        )

        remove.assert_not_called()
        db.upsert_track_meta.assert_called_once_with(
            21, 7, {"cover_path": "covers/track01.png"}
        )
