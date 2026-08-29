"""Tests for the firmware list filters."""

from handler.database import db_firmware_handler


class TestListFirmwareMissingFilter:
    def test_lists_everything_without_the_filter(self, platform, add_firmware):
        add_firmware(platform, "present.bin")
        add_firmware(platform, "gone.bin", missing=True)

        names = [f.file_name for f in db_firmware_handler.list_firmware()]
        assert names == ["gone.bin", "present.bin"]

    def test_missing_true_returns_only_flagged_firmware(self, platform, add_firmware):
        add_firmware(platform, "present.bin")
        add_firmware(platform, "gone.bin", missing=True)

        firmware = db_firmware_handler.list_firmware(missing=True)
        assert [f.file_name for f in firmware] == ["gone.bin"]

    def test_missing_false_excludes_flagged_firmware(self, platform, add_firmware):
        add_firmware(platform, "present.bin")
        add_firmware(platform, "gone.bin", missing=True)

        firmware = db_firmware_handler.list_firmware(missing=False)
        assert [f.file_name for f in firmware] == ["present.bin"]

    def test_combines_with_the_platform_filter(
        self, platform, other_platform, add_firmware
    ):
        add_firmware(platform, "gone.bin", missing=True)
        add_firmware(other_platform, "other-gone.bin", missing=True)

        firmware = db_firmware_handler.list_firmware(
            platform_ids=[platform.id], missing=True
        )
        assert [f.file_name for f in firmware] == ["gone.bin"]

    def test_platform_filter_accepts_several_platforms(
        self, platform, other_platform, add_firmware
    ):
        add_firmware(platform, "gone.bin", missing=True)
        add_firmware(other_platform, "other-gone.bin", missing=True)

        firmware = db_firmware_handler.list_firmware(
            platform_ids=[platform.id, other_platform.id], missing=True
        )
        assert [f.file_name for f in firmware] == ["gone.bin", "other-gone.bin"]

    def test_combines_with_the_hidden_platform_filter(
        self, platform, other_platform, add_firmware
    ):
        add_firmware(platform, "gone.bin", missing=True)
        add_firmware(other_platform, "other-gone.bin", missing=True)

        firmware = db_firmware_handler.list_firmware(
            missing=True, hidden_platform_ids=[other_platform.id]
        )
        assert [f.file_name for f in firmware] == ["gone.bin"]
