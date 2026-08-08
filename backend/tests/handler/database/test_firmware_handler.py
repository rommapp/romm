"""Tests for the firmware list filters.

A scan flags firmware whose file vanished with `missing_from_fs`, but until
issue #4075 nothing could select on that flag, so every consumer (the player's
BIOS list, the platform firmware count) had to take the whole set.
"""

from handler.database import db_firmware_handler, db_platform_handler
from models.firmware import Firmware
from models.platform import Platform


def _add(platform: Platform, file_name: str, missing: bool) -> Firmware:
    return db_firmware_handler.add_firmware(
        Firmware(
            platform_id=platform.id,
            file_name=file_name,
            file_path=f"{platform.fs_slug}/bios",
            file_size_bytes=1,
            crc_hash="crc",
            md5_hash="md5",
            sha1_hash="sha1",
            missing_from_fs=missing,
        )
    )


def _other_platform() -> Platform:
    return db_platform_handler.add_platform(
        Platform(name="other", slug="other_slug", fs_slug="other_slug")
    )


class TestListFirmwareMissingFilter:
    def test_lists_everything_without_the_filter(self, platform):
        _add(platform, "present.bin", missing=False)
        _add(platform, "gone.bin", missing=True)

        names = [f.file_name for f in db_firmware_handler.list_firmware()]
        assert names == ["gone.bin", "present.bin"]

    def test_missing_true_returns_only_flagged_firmware(self, platform):
        _add(platform, "present.bin", missing=False)
        _add(platform, "gone.bin", missing=True)

        firmware = db_firmware_handler.list_firmware(missing=True)
        assert [f.file_name for f in firmware] == ["gone.bin"]

    def test_missing_false_excludes_flagged_firmware(self, platform):
        _add(platform, "present.bin", missing=False)
        _add(platform, "gone.bin", missing=True)

        firmware = db_firmware_handler.list_firmware(missing=False)
        assert [f.file_name for f in firmware] == ["present.bin"]

    def test_combines_with_the_platform_filter(self, platform):
        other = _other_platform()
        _add(platform, "gone.bin", missing=True)
        _add(other, "other-gone.bin", missing=True)

        firmware = db_firmware_handler.list_firmware(
            platform_id=platform.id, missing=True
        )
        assert [f.file_name for f in firmware] == ["gone.bin"]

    def test_combines_with_the_hidden_platform_filter(self, platform):
        other = _other_platform()
        _add(platform, "gone.bin", missing=True)
        _add(other, "other-gone.bin", missing=True)

        firmware = db_firmware_handler.list_firmware(
            missing=True, hidden_platform_ids=[other.id]
        )
        assert [f.file_name for f in firmware] == ["gone.bin"]
