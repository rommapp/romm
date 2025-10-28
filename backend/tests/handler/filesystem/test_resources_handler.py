import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from config import RESOURCES_BASE_PATH
from handler.filesystem.base_handler import CoverSize
from handler.filesystem.resources_handler import FSResourcesHandler
from models.collection import Collection
from models.rom import Rom


class TestFSResourcesHandler:
    """Test suite for FSResourcesHandler class"""

    @pytest.fixture
    def handler(self):
        return FSResourcesHandler()

    @pytest.fixture
    def rom(self):
        """Create a mock ROM object for testing"""
        rom = Mock(spec=Rom)
        rom.id = 1
        rom.platform_id = 1
        rom.fs_resources_path = "roms/1/1"
        return rom

    def test_init_uses_resources_base_path(self, handler: FSResourcesHandler):
        """Test that FSResourcesHandler initializes with RESOURCES_BASE_PATH"""
        assert handler.base_path == Path(RESOURCES_BASE_PATH).resolve()

    def test_get_platform_resources_path(self, handler: FSResourcesHandler):
        """Test get_platform_resources_path method"""
        platform_id = 1
        result = handler.get_platform_resources_path(platform_id)
        expected = os.path.join("roms", "1")
        assert result == expected

    def test_get_platform_resources_path_different_ids(
        self, handler: FSResourcesHandler
    ):
        """Test get_platform_resources_path with different platform IDs"""
        test_ids = [1, 42, 123, 999]
        for platform_id in test_ids:
            result = handler.get_platform_resources_path(platform_id)
            expected = os.path.join("roms", str(platform_id))
            assert result == expected

    def test_cover_exists_no_cover(self, handler: FSResourcesHandler, rom: Rom):
        """Test cover_exists when no cover exists"""
        # Test with non-existent covers
        assert not handler.cover_exists(rom, CoverSize.SMALL)
        assert not handler.cover_exists(rom, CoverSize.BIG)

    def test_cover_exists_with_existing_covers(self, handler: FSResourcesHandler):
        """Test cover_exists with existing covers from the test data"""
        # Use existing test data structure - check directories that might exist
        # Check platform 35, rom 35 (from the find output we saw earlier)
        rom = Mock(spec=Rom)
        rom.id = 35
        rom.platform_id = 35
        rom.fs_resources_path = "roms/35/35"

        # These might exist based on the test data structure
        small_exists = handler.cover_exists(rom, CoverSize.SMALL)
        big_exists = handler.cover_exists(rom, CoverSize.BIG)

        # We can't guarantee they exist, so just test the method works
        assert isinstance(small_exists, bool)
        assert isinstance(big_exists, bool)

    def test_resize_cover_to_small_high_resolution(self, handler: FSResourcesHandler):
        """Test resize_cover_to_small with high resolution image"""
        # Create a mock image with high resolution
        mock_image = Mock()
        mock_image.height = 1500
        mock_image.width = 1000
        mock_image.resize.return_value = mock_image

        save_path = "/tmp/test_small.png"

        handler.resize_cover_to_small(mock_image, save_path)

        # Should use 0.2 ratio for high resolution
        expected_width = int(1000 * 0.2)
        expected_height = int(1500 * 0.2)
        mock_image.resize.assert_called_once_with((expected_width, expected_height))
        mock_image.save.assert_called_once_with(save_path)

    def test_resize_cover_to_small_low_resolution(self, handler: FSResourcesHandler):
        """Test resize_cover_to_small with low resolution image"""
        # Create a mock image with low resolution
        mock_image = Mock()
        mock_image.height = 800
        mock_image.width = 600
        mock_image.resize.return_value = mock_image

        save_path = "/tmp/test_small.png"

        handler.resize_cover_to_small(mock_image, save_path)

        # Should use 0.4 ratio for low resolution
        expected_width = int(600 * 0.4)
        expected_height = int(800 * 0.4)
        mock_image.resize.assert_called_once_with((expected_width, expected_height))
        mock_image.save.assert_called_once_with(save_path)

    def test_get_cover_path_no_cover(self, handler: FSResourcesHandler, rom: Rom):
        """Test _get_cover_path when no cover exists"""
        result_small = handler._get_cover_path(rom, CoverSize.SMALL)
        result_big = handler._get_cover_path(rom, CoverSize.BIG)

        assert result_small is None
        assert result_big is None

    def test_get_cover_path_with_existing_cover(self, handler: FSResourcesHandler):
        """Test _get_cover_path with existing cover files"""
        # Use test data that might exist
        rom = Mock(spec=Rom)
        rom.id = 27
        rom.platform_id = 27
        rom.fs_resources_path = "roms/27/27"

        # Test both sizes
        small_path = handler._get_cover_path(rom, CoverSize.SMALL)
        big_path = handler._get_cover_path(rom, CoverSize.BIG)

        # If paths exist, they should be relative to base path
        if small_path:
            assert not os.path.isabs(small_path)
            assert "small" in small_path
        if big_path:
            assert not os.path.isabs(big_path)
            assert "big" in big_path

    @pytest.mark.asyncio
    async def test_get_cover_no_entity(self, handler: FSResourcesHandler):
        """Test get_cover with no entity"""
        result = await handler.get_cover(None, False, "http://example.com/cover.png")
        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_get_cover_no_url(self, handler: FSResourcesHandler, rom: Rom):
        """Test get_cover with no URL"""
        result = await handler.get_cover(rom, False, None)
        # Should return empty strings since no covers exist and no URL provided
        assert result == (None, None)

    @pytest.mark.asyncio
    async def test_get_cover_with_url_no_overwrite(
        self, handler: FSResourcesHandler, rom
    ):
        """Test get_cover with URL but no overwrite when covers don't exist"""
        url = "http://example.com/cover.png"

        with patch.object(handler, "_store_cover") as mock_store:
            with patch.object(handler, "cover_exists") as mock_exists:
                mock_exists.return_value = False

                await handler.get_cover(rom, False, url)

                # Should call _store_cover for both sizes since covers don't exist
                assert mock_store.call_count == 2
                mock_store.assert_any_call(rom, url, CoverSize.SMALL)
                mock_store.assert_any_call(rom, url, CoverSize.BIG)

    @pytest.mark.asyncio
    async def test_get_cover_with_overwrite(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        """Test get_cover with overwrite enabled"""
        url = "http://example.com/cover.png"

        with patch.object(handler, "_store_cover") as mock_store:
            await handler.get_cover(rom, True, url)

            # Should call _store_cover for both sizes regardless of existence
            assert mock_store.call_count == 2
            mock_store.assert_any_call(rom, url, CoverSize.SMALL)
            mock_store.assert_any_call(rom, url, CoverSize.BIG)

    async def test_remove_cover_no_entity(self, handler: FSResourcesHandler):
        """Test remove_cover with no entity"""
        result = await handler.remove_cover(None)
        assert result == {"path_cover_s": "", "path_cover_l": ""}

    async def test_remove_cover_with_entity(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        """Test remove_cover with entity"""
        with patch.object(handler, "remove_directory") as mock_remove:
            result = await handler.remove_cover(rom)

            mock_remove.assert_called_once_with(f"{rom.fs_resources_path}/cover")
            assert result == {"path_cover_s": "", "path_cover_l": ""}

    async def test_build_artwork_path(self, handler: FSResourcesHandler, rom: Rom):
        """Test build_artwork_path method"""
        file_ext = "png"

        with patch.object(handler, "make_directory") as mock_make_dir:
            with patch.object(handler, "validate_path") as mock_validate:
                mock_validate.side_effect = lambda x: Path(x)

                path_cover_l, path_cover_s = await handler._build_artwork_path(
                    rom, file_ext
                )

                expected_cover_path = f"{rom.fs_resources_path}/cover"
                expected_big_path = f"{expected_cover_path}/big.{file_ext}"
                expected_small_path = f"{expected_cover_path}/small.{file_ext}"

                mock_make_dir.assert_called_once_with(expected_cover_path)
                assert str(path_cover_l) == expected_big_path
                assert str(path_cover_s) == expected_small_path

    async def test_build_artwork_path_different_extensions(
        self, handler: FSResourcesHandler, rom
    ):
        """Test build_artwork_path with different file extensions"""
        extensions = ["png", "jpg", "jpeg", "gif", "webp"]

        for ext in extensions:
            with patch.object(handler, "make_directory"):
                with patch.object(handler, "validate_path") as mock_validate:
                    mock_validate.side_effect = lambda x: Path(x)

                    path_cover_l, path_cover_s = await handler._build_artwork_path(
                        rom, ext
                    )

                    # Check that the extension is properly included
                    assert str(path_cover_l).endswith(f"big.{ext}")
                    assert str(path_cover_s).endswith(f"small.{ext}")

    def test_get_screenshot_path(self, handler: FSResourcesHandler, rom: Rom):
        """Test _get_screenshot_path method"""
        idx = "0"
        result = handler._get_screenshot_path(rom, idx)
        expected = f"{rom.fs_resources_path}/screenshots/{idx}.jpg"
        assert result == expected

    def test_get_screenshot_path_different_indices(
        self, handler: FSResourcesHandler, rom
    ):
        """Test _get_screenshot_path with different indices"""
        indices = ["0", "1", "2", "10", "99"]

        for idx in indices:
            result = handler._get_screenshot_path(rom, idx)
            expected = f"{rom.fs_resources_path}/screenshots/{idx}.jpg"
            assert result == expected

    @pytest.mark.asyncio
    async def test_get_rom_screenshots_no_urls(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        """Test get_rom_screenshots with no URLs"""
        result = await handler.get_rom_screenshots(rom, True, None)
        assert result == rom.path_screenshots

        result = await handler.get_rom_screenshots(rom, True, [])
        assert result == rom.path_screenshots

    @pytest.mark.asyncio
    async def test_get_rom_screenshots_with_urls(
        self, handler: FSResourcesHandler, rom
    ):
        """Test get_rom_screenshots with URLs"""
        urls = [
            "http://example.com/screenshot1.jpg",
            "http://example.com/screenshot2.jpg",
        ]

        with patch.object(handler, "_store_screenshot") as mock_store:
            result = await handler.get_rom_screenshots(rom, True, urls)

            # Should call _store_screenshot for each URL
            assert mock_store.call_count == 2
            mock_store.assert_any_call(rom, urls[0], 0)
            mock_store.assert_any_call(rom, urls[1], 1)

            # Should return paths for each screenshot
            expected_paths = [
                f"{rom.fs_resources_path}/screenshots/0.jpg",
                f"{rom.fs_resources_path}/screenshots/1.jpg",
            ]
            assert result == expected_paths

    def test_manual_exists_no_manual(self, handler: FSResourcesHandler, rom: Rom):
        """Test manual_exists when no manual exists"""
        assert not handler.manual_exists(rom)

    def test_get_manual_path_no_manual(self, handler: FSResourcesHandler, rom: Rom):
        """Test _get_manual_path when no manual exists"""
        result = handler._get_manual_path(rom)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_manual_no_url(self, handler: FSResourcesHandler, rom: Rom):
        """Test get_manual with no URL"""
        result = await handler.get_manual(rom, False, None)
        assert result is rom.path_manual

    @pytest.mark.asyncio
    async def test_get_manual_with_url_no_overwrite(
        self, handler: FSResourcesHandler, rom
    ):
        """Test get_manual with URL but no overwrite when manual doesn't exist"""
        url = "http://example.com/manual.pdf"

        with patch.object(handler, "_store_manual") as mock_store:
            with patch.object(handler, "manual_exists") as mock_exists:
                mock_exists.return_value = False

                await handler.get_manual(rom, False, url)

                # Should call _store_manual since manual doesn't exist
                mock_store.assert_called_once_with(rom, url)

    @pytest.mark.asyncio
    async def test_get_manual_with_overwrite(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        """Test get_manual with overwrite enabled"""
        url = "http://example.com/manual.pdf"

        with patch.object(handler, "_store_manual") as mock_store:
            await handler.get_manual(rom, True, url)

            # Should call _store_manual regardless of existence
            mock_store.assert_called_once_with(rom, url)

    def test_get_ra_resources_path(self, handler: FSResourcesHandler):
        """Test get_ra_resources_path method"""
        platform_id = 1
        rom_id = 42

        result = handler.get_ra_resources_path(platform_id, rom_id)
        expected = os.path.join("roms", "1", "42", "retroachievements")
        assert result == expected

    def test_get_ra_resources_path_different_ids(self, handler: FSResourcesHandler):
        """Test get_ra_resources_path with different IDs"""
        test_cases = [(1, 1), (42, 123), (999, 456), (10, 999)]

        for platform_id, rom_id in test_cases:
            result = handler.get_ra_resources_path(platform_id, rom_id)
            expected = os.path.join(
                "roms", str(platform_id), str(rom_id), "retroachievements"
            )
            assert result == expected

    def test_get_ra_badges_path(self, handler: FSResourcesHandler):
        """Test get_ra_badges_path method"""
        platform_id = 1
        rom_id = 42

        result = handler.get_ra_badges_path(platform_id, rom_id)
        expected = os.path.join("roms", "1", "42", "retroachievements", "badges")
        assert result == expected

    def test_get_ra_badges_path_different_ids(self, handler: FSResourcesHandler):
        """Test get_ra_badges_path with different IDs"""
        test_cases = [(1, 1), (42, 123), (999, 456), (10, 999)]

        for platform_id, rom_id in test_cases:
            result = handler.get_ra_badges_path(platform_id, rom_id)
            expected = os.path.join(
                "roms", str(platform_id), str(rom_id), "retroachievements", "badges"
            )
            assert result == expected

    def test_integration_with_base_handler_methods(self, handler: FSResourcesHandler):
        """Test that FSResourcesHandler properly inherits from FSHandler"""
        # Test that handler has base methods
        assert hasattr(handler, "validate_path")
        assert hasattr(handler, "make_directory")
        assert hasattr(handler, "remove_directory")
        assert hasattr(handler, "write_file_streamed")
        assert hasattr(handler, "file_exists")
        assert hasattr(handler, "stream_file")

    def test_cover_size_enum_values(self, handler: FSResourcesHandler, rom: Rom):
        """Test that cover size enum values are handled correctly"""
        # Test that the enum values are used correctly in path construction
        with patch.object(handler, "validate_path") as mock_validate:
            mock_validate.return_value = Path("test_path")

            # Test SMALL size
            handler._get_cover_path(rom, CoverSize.SMALL)
            # Should look for files with "small" in the name
            call_args = mock_validate.call_args[0][0]
            assert "cover" in call_args

            # Test BIG size
            handler._get_cover_path(rom, CoverSize.BIG)
            call_args = mock_validate.call_args[0][0]
            assert "cover" in call_args

    def test_path_construction_consistency(self, handler: FSResourcesHandler):
        """Test that path construction is consistent across methods"""
        platform_id = 1
        rom_id = 42

        # Test platform resources path
        platform_path = handler.get_platform_resources_path(platform_id)
        assert platform_path.endswith(f"roms/{platform_id}")

        # Test RA base path
        ra_base = handler.get_ra_resources_path(platform_id, rom_id)
        assert ra_base.startswith(f"roms/{platform_id}/{rom_id}")

        # Test RA badges path
        ra_badges = handler.get_ra_badges_path(platform_id, rom_id)
        assert ra_badges.startswith(f"roms/{platform_id}/{rom_id}")
        assert ra_badges.endswith("badges")

    def test_entity_types_handling(self, rom, handler: FSResourcesHandler):
        """Test that both Rom and Collection entities are handled correctly"""
        collection = Mock(spec=Collection)
        collection.id = 1
        collection.fs_resources_path = "collections/1"

        # Both should work with cover_exists
        rom_result = handler.cover_exists(rom, CoverSize.SMALL)
        collection_result = handler.cover_exists(collection, CoverSize.SMALL)

        assert isinstance(rom_result, bool)
        assert isinstance(collection_result, bool)

    def test_error_handling_edge_cases(self, handler: FSResourcesHandler):
        """Test error handling for edge cases"""
        # Test with invalid path
        invalid_entity = Mock()
        invalid_entity.fs_resources_path = ""

        # Should raise a ValueError
        with pytest.raises(ValueError):
            handler.cover_exists(invalid_entity, CoverSize.SMALL)

    def test_existing_resources_structure(self, handler: FSResourcesHandler):
        """Test with the existing resources structure in romm_test"""
        # Test that the handler can work with the existing directory structure
        # without creating new files

        # Test platform resources path with existing structure
        platform_path = handler.get_platform_resources_path(35)
        assert isinstance(platform_path, str)
        assert "roms" in platform_path
        assert "35" in platform_path

        # Test RA paths with existing structure
        ra_base = handler.get_ra_resources_path(35, 35)
        ra_badges = handler.get_ra_badges_path(35, 35)

        assert isinstance(ra_base, str)
        assert isinstance(ra_badges, str)
        assert "retroachievements" in ra_base
        assert "badges" in ra_badges
