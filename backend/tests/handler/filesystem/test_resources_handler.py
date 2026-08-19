import asyncio
import errno
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from PIL import Image

import adapters.services.screenscraper as ss_module
from adapters.services.screenscraper import (
    SS_DEFAULT_MAX_THREADS,
    SS_DEFAULT_MEDIA_TIMEOUT,
)
from config import RESOURCES_BASE_PATH
from config.config_manager import MetadataMediaType
from handler.filesystem.base_handler import CoverSize
from handler.filesystem.resources_handler import (
    FSResourcesHandler,
    _check_content_type,
    _content_type_essence,
    _is_chroma_key_placeholder,
)
from models.collection import Collection
from models.rom import Rom
from utils.rate_limiter import ConcurrencyLimiter, RateLimiter


class TestContentTypeEssence:
    """Tests for the _content_type_essence helper."""

    def test_simple_mime_type(self):
        assert _content_type_essence("image/png") == "image/png"

    def test_with_charset_parameter(self):
        assert _content_type_essence("text/html; charset=utf-8") == "text/html"

    def test_with_multiple_parameters(self):
        assert (
            _content_type_essence("text/html; charset=utf-8; boundary=something")
            == "text/html"
        )

    def test_leading_whitespace(self):
        assert _content_type_essence("  image/jpeg") == "image/jpeg"

    def test_trailing_whitespace(self):
        assert _content_type_essence("image/jpeg  ") == "image/jpeg"

    def test_whitespace_around_semicolon(self):
        assert _content_type_essence("image/jpeg ; charset=utf-8") == "image/jpeg"

    def test_uppercase_normalized_to_lower(self):
        assert _content_type_essence("Image/PNG") == "image/png"

    def test_mixed_case_with_params(self):
        assert (
            _content_type_essence("Application/PDF; charset=utf-8") == "application/pdf"
        )

    def test_utf8_bom_prefix(self):
        assert _content_type_essence("\ufeffimage/png") == "image/png"

    def test_utf8_bom_with_params(self):
        assert (
            _content_type_essence("\ufeffapplication/pdf; charset=utf-8")
            == "application/pdf"
        )

    def test_empty_string(self):
        assert _content_type_essence("") == ""

    def test_none_like_empty(self):
        """Falsy input returns empty string."""
        assert _content_type_essence("") == ""

    def test_only_whitespace(self):
        assert _content_type_essence("   ") == ""

    def test_octet_stream(self):
        assert (
            _content_type_essence("application/octet-stream")
            == "application/octet-stream"
        )

    def test_force_download(self):
        assert (
            _content_type_essence("application/force-download")
            == "application/force-download"
        )


class TestCheckContentType:
    """Tests for the _check_content_type helper."""

    @staticmethod
    def _make_response(content_type: str | None) -> httpx.Response:
        headers = {}
        if content_type is not None:
            headers["content-type"] = content_type
        return httpx.Response(200, headers=headers)

    def test_valid_image_prefix(self):
        resp = self._make_response("image/png")
        assert _check_content_type(resp, ("image/",), "cover") is True

    def test_valid_image_with_charset(self):
        resp = self._make_response("image/jpeg; charset=utf-8")
        assert _check_content_type(resp, ("image/",), "cover") is True

    def test_valid_pdf(self):
        resp = self._make_response("application/pdf")
        assert (
            _check_content_type(
                resp,
                ("application/pdf", "application/octet-stream"),
                "manual",
            )
            is True
        )

    def test_valid_octet_stream(self):
        resp = self._make_response("application/octet-stream")
        assert (
            _check_content_type(
                resp,
                ("application/pdf", "application/octet-stream"),
                "manual",
            )
            is True
        )

    def test_wrong_content_type(self):
        resp = self._make_response("text/html")
        assert _check_content_type(resp, ("image/",), "cover") is False

    def test_missing_header(self):
        resp = self._make_response(None)
        assert _check_content_type(resp, ("image/",), "cover") is False

    def test_empty_header(self):
        resp = self._make_response("")
        assert _check_content_type(resp, ("image/",), "cover") is False

    def test_leading_whitespace_still_matches(self):
        resp = self._make_response("  image/png")
        assert _check_content_type(resp, ("image/",), "cover") is True

    def test_bom_still_matches(self):
        # httpx rejects non-ASCII header values, so mock the response
        resp = Mock(spec=httpx.Response)
        resp.headers = {"content-type": "\ufeffimage/png"}
        assert _check_content_type(resp, ("image/",), "cover") is True

    def test_case_insensitive(self):
        resp = self._make_response("Image/PNG")
        assert _check_content_type(resp, ("image/",), "cover") is True


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

    def test_cover_exists_no_cover(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        """Test cover_exists when no cover exists"""
        # Point at an isolated empty tree so a cover leaked by another test
        # (shared RESOURCES_BASE_PATH) can't make this assertion flaky.
        handler.base_path = tmp_path
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

    def test_get_cover_path_no_cover(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        """Test _get_cover_path when no cover exists"""
        handler.base_path = tmp_path
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
    async def test_get_cover_no_url(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        """Test get_cover with no URL"""
        handler.base_path = tmp_path
        result = await handler.get_cover(rom, False, None)
        # Should return empty strings since no covers exist and no URL provided
        assert result == (None, None)

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

    @pytest.mark.parametrize("ext", [".pdf", ".md"])
    def test_manual_exists_finds_extension(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path, ext: str
    ):
        """manual_exists locates both PDF and Markdown manuals."""
        handler.base_path = tmp_path
        manual_dir = tmp_path / rom.fs_resources_path / "manual"
        manual_dir.mkdir(parents=True)
        (manual_dir / f"{rom.id}{ext}").write_bytes(b"manual")

        assert handler.manual_exists(rom)

    @pytest.mark.parametrize("ext", [".pdf", ".md"])
    def test_get_manual_path_finds_extension(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path, ext: str
    ):
        """_get_manual_path returns the relative path for PDF and Markdown."""
        handler.base_path = tmp_path
        manual_dir = tmp_path / rom.fs_resources_path / "manual"
        manual_dir.mkdir(parents=True)
        (manual_dir / f"{rom.id}{ext}").write_bytes(b"manual")

        result = handler._get_manual_path(rom)
        assert result == f"{rom.fs_resources_path}/manual/{rom.id}{ext}"

    @pytest.mark.parametrize("ext", [".part", ".bak", ".tmp", ".txt"])
    def test_manual_exists_ignores_disallowed_extensions(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path, ext: str
    ):
        """Files that aren't PDF or Markdown must not be treated as manuals."""
        handler.base_path = tmp_path
        manual_dir = tmp_path / rom.fs_resources_path / "manual"
        manual_dir.mkdir(parents=True)
        (manual_dir / f"{rom.id}{ext}").write_bytes(b"not a manual")

        assert not handler.manual_exists(rom)
        assert handler._get_manual_path(rom) is None

    def test_get_manual_path_prefers_newest_when_multiple_exist(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        """When several allowed manuals coexist, the newest one wins."""
        handler.base_path = tmp_path
        manual_dir = tmp_path / rom.fs_resources_path / "manual"
        manual_dir.mkdir(parents=True)

        older = manual_dir / f"{rom.id}.md"
        newer = manual_dir / f"{rom.id}.pdf"
        older.write_bytes(b"old manual")
        newer.write_bytes(b"new manual")
        os.utime(older, (1000, 1000))
        os.utime(newer, (2000, 2000))

        result = handler._get_manual_path(rom)
        assert result == f"{rom.fs_resources_path}/manual/{rom.id}.pdf"

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


class TestChromaKeyDetection:
    """Tests for ScreenScraper chroma-key green placeholder handling."""

    @pytest.fixture
    def handler(self):
        return FSResourcesHandler()

    def _write_image(self, path: Path, color: tuple[int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), color).save(path)

    def test_detects_solid_chroma_key_green(self, tmp_path):
        image = tmp_path / "green.png"
        self._write_image(image, (0, 255, 0))
        assert _is_chroma_key_placeholder(image) is True

    def test_detects_near_chroma_key_green(self, tmp_path):
        # Within tolerance of pure #00FF00.
        image = tmp_path / "near_green.png"
        self._write_image(image, (10, 250, 8))
        assert _is_chroma_key_placeholder(image) is True

    def test_ignores_normal_artwork(self, tmp_path):
        image = tmp_path / "cover.png"
        self._write_image(image, (85, 62, 152))  # the placeholder purple
        assert _is_chroma_key_placeholder(image) is False

    def test_ignores_forest_green_artwork(self, tmp_path):
        # A dark/natural green cover must not be mistaken for the chroma key.
        image = tmp_path / "forest.png"
        self._write_image(image, (34, 139, 34))
        assert _is_chroma_key_placeholder(image) is False

    def test_ignores_non_image_file(self, tmp_path):
        not_an_image = tmp_path / "data.bin"
        not_an_image.write_bytes(b"not an image")
        assert _is_chroma_key_placeholder(not_an_image) is False

    @pytest.mark.asyncio
    async def test_discard_removes_chroma_key_file(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        rel = "roms/1/1/box2d_back/box2d_back.png"
        self._write_image(tmp_path / rel, (0, 255, 0))

        discarded = await handler._discard_if_chroma_key(rel)

        assert discarded is True
        assert not (tmp_path / rel).exists()

    @pytest.mark.asyncio
    async def test_discard_keeps_real_artwork(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        rel = "roms/1/1/box2d_back/box2d_back.png"
        self._write_image(tmp_path / rel, (85, 62, 152))

        discarded = await handler._discard_if_chroma_key(rel)

        assert discarded is False
        assert (tmp_path / rel).exists()

    @pytest.mark.asyncio
    async def test_discard_missing_file_is_noop(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        assert await handler._discard_if_chroma_key("roms/1/1/nope.png") is False

    @pytest.mark.asyncio
    async def test_store_media_file_discards_existing_chroma_key(
        self, handler: FSResourcesHandler, tmp_path
    ):
        # A green placeholder already on disk is dropped on rescan, so the box
        # face falls back to the dark placeholder instead of rendering green.
        handler.base_path = tmp_path
        rel = "roms/1/1/box2d_back/box2d_back.png"
        self._write_image(tmp_path / rel, (0, 255, 0))

        await handler.store_media_file("http://example.com/x.png", rel)

        assert not (tmp_path / rel).exists()

    @pytest.mark.asyncio
    async def test_store_media_file_keeps_existing_real_art(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        rel = "roms/1/1/box2d_back/box2d_back.png"
        self._write_image(tmp_path / rel, (85, 62, 152))

        await handler.store_media_file("http://example.com/x.png", rel)

        assert (tmp_path / rel).exists()


class TestStoreMediaFileResult:
    """store_media_file reports whether the media actually landed on disk, so
    callers can drop the recorded path instead of pointing at a missing file."""

    @pytest.fixture
    def handler(self):
        return FSResourcesHandler()

    @pytest.mark.asyncio
    async def test_returns_true_for_downloaded_file(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        rel = "roms/1/1/box2d_back/box2d_back.png"

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = _FakeHttpxClient(_FakeResponse())
            assert await handler.store_media_file("http://example.com/x.png", rel)

        assert (tmp_path / rel).exists()

    @pytest.mark.asyncio
    async def test_returns_true_for_pre_existing_file(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        rel = "roms/1/1/box2d_back/box2d_back.png"
        (tmp_path / rel).parent.mkdir(parents=True)
        (tmp_path / rel).write_bytes(b"art")

        assert await handler.store_media_file("http://example.com/x.png", rel)

    @pytest.mark.asyncio
    async def test_returns_false_on_error_response(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        response = _FakeResponse()
        response.status_code = 404

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = _FakeHttpxClient(response)
            stored = await handler.store_media_file(
                "http://example.com/x.png", "roms/1/1/box2d_back/box2d_back.png"
            )

        assert stored is False

    @pytest.mark.asyncio
    async def test_returns_false_on_unexpected_content_type(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        response = _FakeResponse()
        response.headers = {"content-type": "text/html"}

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = _FakeHttpxClient(response)
            stored = await handler.store_media_file(
                "http://example.com/x.png", "roms/1/1/box2d_back/box2d_back.png"
            )

        assert stored is False

    @pytest.mark.asyncio
    async def test_returns_false_on_transport_error(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            client = Mock()
            client.stream.side_effect = httpx.ConnectError("no route")
            mock_ctx.get.return_value = client
            stored = await handler.store_media_file(
                "http://example.com/x.png", "roms/1/1/box2d_back/box2d_back.png"
            )

        assert stored is False

    @pytest.mark.asyncio
    async def test_returns_false_for_discarded_chroma_key(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        rel = "roms/1/1/box2d_back/box2d_back.png"
        (tmp_path / rel).parent.mkdir(parents=True)
        Image.new("RGB", (64, 64), (0, 255, 0)).save(tmp_path / rel)

        assert await handler.store_media_file("http://example.com/x.png", rel) is False

    @pytest.mark.asyncio
    async def test_returns_false_for_unresolvable_local_uri(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        stored = await handler.store_media_file(
            "launchbox-file://Videos/NES/missing.mp4", "roms/1/1/video/video.mp4"
        )

        assert stored is False


class TestStoreMetadataMedia:
    """Recorded media paths must not survive a download that didn't produce a
    file, or exports and artwork URLs would point at nothing."""

    @pytest.fixture
    def handler(self):
        return FSResourcesHandler()

    @pytest.mark.asyncio
    async def test_clears_paths_for_media_that_did_not_land(
        self, handler: FSResourcesHandler
    ):
        metadata = {
            "box2d_back_url": "http://example.com/back.png",
            "box2d_back_path": "roms/1/1/box2d_back/box2d_back.png",
            "fanart_url": "http://example.com/fanart.png",
            "fanart_path": "roms/1/1/fanart/fanart.png",
        }

        async def fake_store(_url: str, dest_path: str) -> bool:
            return "fanart" in dest_path

        with patch.object(handler, "store_media_file", side_effect=fake_store):
            changed = await handler.store_metadata_media(
                metadata,
                [MetadataMediaType.BOX2D_BACK, MetadataMediaType.FANART],
            )

        assert changed is True
        assert metadata["box2d_back_path"] is None
        assert metadata["fanart_path"] == "roms/1/1/fanart/fanart.png"
        # The URL is kept so a later scan can retry the download
        assert metadata["box2d_back_url"] == "http://example.com/back.png"

    @pytest.mark.asyncio
    async def test_leaves_metadata_untouched_when_all_media_lands(
        self, handler: FSResourcesHandler
    ):
        metadata = {
            "fanart_url": "http://example.com/fanart.png",
            "fanart_path": "roms/1/1/fanart/fanart.png",
        }

        with patch.object(handler, "store_media_file", return_value=True):
            changed = await handler.store_metadata_media(
                metadata, [MetadataMediaType.FANART]
            )

        assert changed is False
        assert metadata["fanart_path"] == "roms/1/1/fanart/fanart.png"

    @pytest.mark.asyncio
    async def test_skips_media_types_without_a_path(self, handler: FSResourcesHandler):
        metadata = {"fanart_url": "http://example.com/fanart.png"}

        with patch.object(handler, "store_media_file") as store_mock:
            changed = await handler.store_metadata_media(
                metadata,
                [MetadataMediaType.FANART, MetadataMediaType.BOX2D_BACK],
            )

        assert changed is False
        store_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_clears_a_urlless_path_when_the_file_is_missing(
        self, handler: FSResourcesHandler, tmp_path
    ):
        # A path with no URL can never be fetched, so it must not survive when
        # the file it names isn't there.
        handler.base_path = tmp_path
        metadata = {"fanart_path": "roms/1/1/fanart/fanart.png"}

        changed = await handler.store_metadata_media(
            metadata, [MetadataMediaType.FANART]
        )

        assert changed is True
        assert metadata["fanart_path"] is None

    @pytest.mark.asyncio
    async def test_keeps_a_urlless_path_when_the_file_exists(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        rel = "roms/1/1/fanart/fanart.png"
        (tmp_path / rel).parent.mkdir(parents=True)
        (tmp_path / rel).write_bytes(b"art")
        metadata = {"fanart_path": rel}

        changed = await handler.store_metadata_media(
            metadata, [MetadataMediaType.FANART]
        )

        assert changed is False
        assert metadata["fanart_path"] == rel

    @pytest.mark.asyncio
    async def test_applies_the_url_transform(self, handler: FSResourcesHandler):
        metadata = {
            "fanart_url": "http://example.com/fanart.png",
            "fanart_path": "roms/1/1/fanart/fanart.png",
        }

        with patch.object(handler, "store_media_file", return_value=True) as store_mock:
            await handler.store_metadata_media(
                metadata,
                [MetadataMediaType.FANART],
                lambda url: f"{url}?ssid=user",
            )

        store_mock.assert_awaited_once_with(
            "http://example.com/fanart.png?ssid=user", "roms/1/1/fanart/fanart.png"
        )


class _FakeResponse:
    """Minimal stand-in for an httpx streaming response."""

    def __init__(self):
        self.status_code = 200
        self.headers = {"content-type": "image/png"}

    async def aiter_raw(self):
        yield b"partial"


class _DroppedResponse:
    """Streams one chunk, then drops the connection mid-transfer."""

    def __init__(self):
        self.status_code = 200
        self.headers = {"content-type": "image/png"}

    async def aiter_raw(self):
        yield b"partial"
        raise httpx.ReadError("connection reset")


class _FakeStreamContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *_args):
        return False


class _FakeHttpxClient:
    def __init__(self, response):
        self._response = response

    def stream(self, *_args, **_kwargs):
        return _FakeStreamContext(self._response)


class _EnospcResponse:
    """Streams one chunk, then fails the way a full disk does."""

    def __init__(self, content_type: str = "image/png"):
        self.status_code = 200
        self.headers = {"content-type": content_type}

    async def aiter_raw(self):
        yield b"partial"
        raise OSError(errno.ENOSPC, "No space left on device")


class TestDiskFullHandling:
    """Resource writes must not leave truncated files when the disk fills up."""

    @pytest.fixture
    def handler(self):
        return FSResourcesHandler()

    @pytest.fixture
    def rom(self):
        rom = Mock(spec=Rom)
        rom.id = 1
        rom.platform_id = 1
        rom.fs_resources_path = "roms/1/1"
        return rom

    @pytest.mark.asyncio
    async def test_discard_partial_file_removes_file(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        rel = "roms/1/1/cover/big.png"
        (tmp_path / rel).parent.mkdir(parents=True)
        (tmp_path / rel).write_bytes(b"truncated")

        await handler._discard_partial_file(rel)

        assert not (tmp_path / rel).exists()

    @pytest.mark.asyncio
    async def test_discard_partial_file_missing_is_noop(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        await handler._discard_partial_file("roms/1/1/cover/big.png")

    @pytest.mark.asyncio
    async def test_discard_partial_file_survives_removal_failure(
        self, handler: FSResourcesHandler, tmp_path
    ):
        # Cleanup runs inside an error path, so it must never mask the
        # original failure with one of its own.
        handler.base_path = tmp_path
        rel = "roms/1/1/cover/big.png"
        (tmp_path / rel).parent.mkdir(parents=True)
        (tmp_path / rel).write_bytes(b"truncated")

        with patch.object(handler, "remove_file", side_effect=OSError("read-only")):
            await handler._discard_partial_file(rel)

    @pytest.mark.asyncio
    async def test_store_cover_discards_partial_download(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        handler.base_path = tmp_path
        target = tmp_path / "roms/1/1/cover/big.png"

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = _FakeHttpxClient(_EnospcResponse())

            await handler._store_cover(rom, "http://example.com/cover.png")

        assert not target.exists()

    @pytest.mark.asyncio
    async def test_store_cover_discards_partial_on_dropped_connection(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        # A stream that dies mid-transfer leaves the same truncated file a
        # full disk does, and must be cleaned up the same way.
        handler.base_path = tmp_path
        target = tmp_path / "roms/1/1/cover/big.png"

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = _FakeHttpxClient(_DroppedResponse())

            await handler._store_cover(rom, "http://example.com/cover.png")

        assert not target.exists()

    @pytest.mark.asyncio
    async def test_store_cover_keeps_existing_file_when_refresh_dies(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        # Refreshing a cover that is already on disk must not cost the good copy
        # when the transfer dies: the stream lands in a temp file, so the
        # existing bytes survive untouched.
        handler.base_path = tmp_path
        target = tmp_path / "roms/1/1/cover/big.png"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"the good cover")

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = _FakeHttpxClient(_DroppedResponse())

            await handler._store_cover(rom, "http://example.com/cover.png")

        assert target.read_bytes() == b"the good cover"

    @pytest.mark.asyncio
    async def test_cancelled_download_leaves_no_temp_file(
        self, handler: FSResourcesHandler, tmp_path
    ):
        # Stopping a scan raises CancelledError, which derives from
        # BaseException. Cleanup has to catch it or every cancel strands a
        # temp file in the resource directory.
        handler.base_path = tmp_path
        cover_dir = tmp_path / "roms/1/1/cover"
        cover_dir.mkdir(parents=True)

        with pytest.raises(asyncio.CancelledError):
            async with handler.write_file_streamed(
                path="roms/1/1/cover", filename="big.png"
            ) as f:
                await f.write(b"partial")
                raise asyncio.CancelledError()

        assert list(cover_dir.iterdir()) == []

    @pytest.mark.asyncio
    async def test_interrupted_download_leaves_no_temp_file(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        # A temp file left in the cover directory would be served as a resource
        # and would accumulate one per failed scan.
        handler.base_path = tmp_path
        cover_dir = tmp_path / "roms/1/1/cover"

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = _FakeHttpxClient(_DroppedResponse())

            await handler._store_cover(rom, "http://example.com/cover.png")

        assert list(cover_dir.iterdir()) == []

    @pytest.mark.asyncio
    async def test_store_ra_badge_discards_partial_download(
        self, handler: FSResourcesHandler, tmp_path
    ):
        # Badges are skipped when already present, so a truncated one would
        # never be refetched.
        handler.base_path = tmp_path
        rel = "roms/1/1/ra/badge.png"
        target = tmp_path / rel

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = _FakeHttpxClient(_EnospcResponse())

            await handler.store_ra_badge("http://example.com/badge.png", rel)

        assert not target.exists()


class _SlotAwareClient:
    """Records the limiter state and timeout seen at the moment of the request."""

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []

    def stream(self, *_args, **kwargs):
        self.calls.append(
            {
                "timeout": kwargs.get("timeout"),
                "in_flight": ss_module._concurrency_limiter.in_flight,
            }
        )
        return _FakeStreamContext(self._response)


class TestScreenScraperMediaThrottling:
    """ScreenScraper counts media downloads against the same per-account thread
    allowance as API calls, so they must share its limiter instead of bypassing
    it (which is what let a multi-worker scan overrun the account)."""

    @pytest.fixture(autouse=True)
    def _isolate_limiters(self, monkeypatch):
        """Swap in fresh limiters so these tests neither sleep on the real
        per-minute pacing nor leave reserved slots behind for later tests."""
        monkeypatch.setattr(ss_module, "_rate_limiter", RateLimiter(1_000))
        monkeypatch.setattr(
            ss_module,
            "_concurrency_limiter",
            ConcurrencyLimiter(SS_DEFAULT_MAX_THREADS),
        )

    @pytest.fixture
    def handler(self):
        return FSResourcesHandler()

    @pytest.fixture
    def rom(self):
        rom = Mock(spec=Rom)
        rom.id = 1
        rom.platform_id = 1
        rom.fs_resources_path = "roms/1/1"
        return rom

    @pytest.mark.asyncio
    async def test_media_file_download_holds_a_screenscraper_slot(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        client = _SlotAwareClient(_FakeResponse())

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = client
            await handler.store_media_file(
                "https://www.screenscraper.fr/image.php?gameid=1",
                "roms/1/1/box2d/big.png",
            )

        assert client.calls == [
            {"timeout": SS_DEFAULT_MEDIA_TIMEOUT, "in_flight": 1},
        ]
        assert ss_module._concurrency_limiter.in_flight == 0

    @pytest.mark.asyncio
    async def test_cover_download_holds_a_screenscraper_slot(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        handler.base_path = tmp_path
        client = _SlotAwareClient(_FakeResponse())

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = client
            await handler._store_cover(
                rom, "https://www.screenscraper.fr/image.php?gameid=1"
            )

        assert client.calls[0]["in_flight"] == 1
        assert ss_module._concurrency_limiter.in_flight == 0

    @pytest.mark.asyncio
    async def test_manual_download_holds_a_screenscraper_slot(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        handler.base_path = tmp_path
        response = _FakeResponse()
        response.headers = {"content-type": "application/pdf"}
        client = _SlotAwareClient(response)

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = client
            await handler._store_manual(
                rom, "https://www.screenscraper.fr/media.php?media=manual"
            )

        assert client.calls[0]["in_flight"] == 1

    @pytest.mark.asyncio
    async def test_screenshot_download_holds_a_screenscraper_slot(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        handler.base_path = tmp_path
        client = _SlotAwareClient(_FakeResponse())

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = client
            await handler._store_screenshot(
                rom, "https://www.screenscraper.fr/image.php?media=ss", 0
            )

        assert client.calls[0]["in_flight"] == 1

    @pytest.mark.asyncio
    async def test_other_providers_are_not_throttled(
        self, handler: FSResourcesHandler, tmp_path
    ):
        handler.base_path = tmp_path
        client = _SlotAwareClient(_FakeResponse())

        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = client
            await handler.store_media_file(
                "https://cdn.example.com/cover.png", "roms/1/1/box2d/big.png"
            )

        assert client.calls == [
            {"timeout": SS_DEFAULT_MEDIA_TIMEOUT, "in_flight": 0},
        ]


COVER_URL = "http://example.com/cover.png"


def _png_bytes(
    size: tuple[int, int] = (900, 1200), color: tuple[int, int, int] = (85, 62, 152)
) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


class _CountingResponse:
    def __init__(self, payload: bytes):
        self.status_code = 200
        self.headers = {"content-type": "image/png"}
        self._payload = payload

    async def aiter_raw(self):
        yield self._payload


class _CountingClient:
    """Records every request, so a redundant refetch of a cover is visible."""

    def __init__(self, payload: bytes):
        self._payload = payload
        self.requests: list[str] = []

    def stream(self, _method: str, url: str, **_kwargs):
        self.requests.append(url)
        return _FakeStreamContext(_CountingResponse(self._payload))


class TestCoverSingleFetch:
    """A cover must be fetched exactly once.

    `small` is a downscale of `big`, so a second request for the same URL only
    re-downloads bytes RomM already holds. That doubles cover bandwidth, and on
    ScreenScraper burns a second billable api2 request per cover.
    """

    @pytest.fixture
    def handler(self, tmp_path):
        handler = FSResourcesHandler()
        handler.base_path = tmp_path
        return handler

    @pytest.fixture
    def rom(self):
        rom = Mock(spec=Rom)
        rom.id = 1
        rom.platform_id = 1
        rom.fs_resources_path = "roms/1/1"
        return rom

    @staticmethod
    def _cover_dir(handler: FSResourcesHandler, entity) -> Path:
        return handler.base_path / entity.fs_resources_path / "cover"

    @staticmethod
    def _image_size(path: Path) -> tuple[int, int]:
        with Image.open(path) as img:
            return img.size

    @staticmethod
    def _write_cover(
        path: Path,
        color: tuple[int, int, int] = (10, 20, 30),
        size: tuple[int, int] = (16, 16),
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color).save(path)

    @staticmethod
    async def _get_cover(
        handler: FSResourcesHandler,
        entity,
        overwrite: bool,
        client,
        url: str | None = COVER_URL,
    ) -> tuple[str | None, str | None]:
        with patch("handler.filesystem.resources_handler.ctx_httpx_client") as mock_ctx:
            mock_ctx.get.return_value = client
            return await handler.get_cover(entity, overwrite, url)

    async def test_fetches_the_cover_once_when_no_covers_exist(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        client = _CountingClient(_png_bytes())

        path_small, path_big = await self._get_cover(handler, rom, False, client)

        assert client.requests == [COVER_URL]
        cover_dir = self._cover_dir(handler, rom)
        assert self._image_size(cover_dir / "big.png") == (900, 1200)
        assert self._image_size(cover_dir / "small.png") == (180, 240)
        assert path_big == "roms/1/1/cover/big.png"
        assert path_small == "roms/1/1/cover/small.png"

    async def test_fetches_the_cover_once_when_overwriting(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        cover_dir = self._cover_dir(handler, rom)
        self._write_cover(cover_dir / "big.png")
        self._write_cover(cover_dir / "small.png")
        client = _CountingClient(_png_bytes())

        await self._get_cover(handler, rom, True, client)

        assert client.requests == [COVER_URL]
        assert self._image_size(cover_dir / "big.png") == (900, 1200)
        assert self._image_size(cover_dir / "small.png") == (180, 240)

    async def test_does_not_fetch_when_both_covers_exist(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        cover_dir = self._cover_dir(handler, rom)
        self._write_cover(cover_dir / "big.png")
        self._write_cover(cover_dir / "small.png")
        client = _CountingClient(_png_bytes())

        path_small, path_big = await self._get_cover(handler, rom, False, client)

        assert client.requests == []
        assert path_small == "roms/1/1/cover/small.png"
        assert path_big == "roms/1/1/cover/big.png"

    async def test_fetches_once_when_only_the_small_cover_exists(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        cover_dir = self._cover_dir(handler, rom)
        self._write_cover(cover_dir / "small.png")
        client = _CountingClient(_png_bytes())

        await self._get_cover(handler, rom, False, client)

        assert client.requests == [COVER_URL]
        assert self._image_size(cover_dir / "big.png") == (900, 1200)
        assert self._image_size(cover_dir / "small.png") == (180, 240)

    async def test_rebuilds_a_missing_small_cover_without_fetching(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        cover_dir = self._cover_dir(handler, rom)
        self._write_cover(cover_dir / "big.png", size=(900, 1200))
        before = (cover_dir / "big.png").read_bytes()
        client = _CountingClient(_png_bytes())

        path_small, path_big = await self._get_cover(handler, rom, False, client)

        assert client.requests == []
        assert (cover_dir / "big.png").read_bytes() == before
        assert self._image_size(cover_dir / "small.png") == (180, 240)
        assert path_big == "roms/1/1/cover/big.png"
        assert path_small == "roms/1/1/cover/small.png"

    async def test_a_broken_provider_cannot_destroy_an_existing_large_cover(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        # Fetching into big.png to recover a missing small.png would put a good
        # large cover at the mercy of the download.
        cover_dir = self._cover_dir(handler, rom)
        self._write_cover(cover_dir / "big.png", size=(900, 1200))
        before = (cover_dir / "big.png").read_bytes()

        path_small, path_big = await self._get_cover(
            handler, rom, False, _FakeHttpxClient(_DroppedResponse())
        )

        assert (cover_dir / "big.png").read_bytes() == before
        assert path_big == "roms/1/1/cover/big.png"
        assert path_small == "roms/1/1/cover/small.png"

    async def test_rebuilds_the_small_cover_with_the_large_covers_extension(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        cover_dir = self._cover_dir(handler, rom)
        self._write_cover(cover_dir / "big.jpg", size=(900, 1200))
        client = _CountingClient(_png_bytes())

        path_small, _ = await self._get_cover(handler, rom, False, client)

        assert client.requests == []
        assert self._image_size(cover_dir / "small.jpg") == (180, 240)
        assert path_small == "roms/1/1/cover/small.jpg"

    async def test_leaves_an_unreadable_large_cover_in_place(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        cover_dir = self._cover_dir(handler, rom)
        cover_dir.mkdir(parents=True)
        (cover_dir / "big.png").write_bytes(b"not an image")
        client = _CountingClient(_png_bytes())

        path_small, path_big = await self._get_cover(handler, rom, False, client)

        assert client.requests == []
        assert (cover_dir / "big.png").exists()
        assert not (cover_dir / "small.png").exists()
        assert path_big == "roms/1/1/cover/big.png"
        assert path_small is None

    async def test_does_not_fetch_without_a_url(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        cover_dir = self._cover_dir(handler, rom)
        self._write_cover(cover_dir / "big.png")
        self._write_cover(cover_dir / "small.png")
        client = _CountingClient(_png_bytes())

        path_small, path_big = await self._get_cover(handler, rom, True, client, None)

        assert client.requests == []
        assert path_small == "roms/1/1/cover/small.png"
        assert path_big == "roms/1/1/cover/big.png"

    async def test_copies_a_local_cover_once(
        self, handler: FSResourcesHandler, rom: Rom, tmp_path
    ):
        source = tmp_path / "library" / "art.png"
        source.parent.mkdir(parents=True)
        Image.new("RGB", (900, 1200), (85, 62, 152)).save(source)

        copied_to: list[str] = []
        original_copy = handler.copy_file

        async def counting_copy(src, dest, allow_link=False):
            copied_to.append(dest)
            await original_copy(src, dest, allow_link=allow_link)

        with (
            patch(
                "handler.filesystem.resources_handler._resolve_local_file_uri",
                return_value=source,
            ),
            patch.object(
                handler, "copy_file", new=AsyncMock(side_effect=counting_copy)
            ),
        ):
            await handler.get_cover(rom, False, "file://art.png")

        assert copied_to == ["roms/1/1/cover/big.png"]
        cover_dir = self._cover_dir(handler, rom)
        assert self._image_size(cover_dir / "big.png") == (900, 1200)
        assert self._image_size(cover_dir / "small.png") == (180, 240)
        # A hardlinked destination would be rewritten in place by a later scan,
        # mutating the user's source image.
        assert (cover_dir / "big.png").stat().st_nlink == 1
        assert self._image_size(source) == (900, 1200)

    async def test_discards_both_sizes_for_a_chroma_key_placeholder(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        cover_dir = self._cover_dir(handler, rom)
        self._write_cover(cover_dir / "small.png")
        client = _CountingClient(_png_bytes(color=(0, 255, 0)))

        result = await self._get_cover(handler, rom, True, client)

        assert client.requests == [COVER_URL]
        assert not (cover_dir / "big.png").exists()
        assert not (cover_dir / "small.png").exists()
        assert result == (None, None)

    async def test_leaves_no_cover_behind_on_a_dropped_connection(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        result = await self._get_cover(
            handler, rom, True, _FakeHttpxClient(_DroppedResponse())
        )

        cover_dir = self._cover_dir(handler, rom)
        assert not (cover_dir / "big.png").exists()
        assert not (cover_dir / "small.png").exists()
        assert result == (None, None)

    async def test_leaves_no_cover_behind_for_undecodable_bytes(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        # A file PIL can't open satisfies cover_exists(), so leaving it would
        # stop every later scan from refetching a working cover.
        client = _CountingClient(b"not an image")

        result = await self._get_cover(handler, rom, True, client)

        assert client.requests == [COVER_URL]
        cover_dir = self._cover_dir(handler, rom)
        assert not (cover_dir / "big.png").exists()
        assert not (cover_dir / "small.png").exists()
        assert result == (None, None)

    async def test_converts_both_sizes_to_webp(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        client = _CountingClient(_png_bytes())

        with patch(
            "handler.filesystem.resources_handler.ENABLE_SCHEDULED_CONVERT_IMAGES_TO_WEBP",
            True,
        ):
            await self._get_cover(handler, rom, False, client)

        cover_dir = self._cover_dir(handler, rom)
        assert (cover_dir / "big.webp").exists()
        assert (cover_dir / "small.webp").exists()

    async def test_low_resolution_cover_uses_the_larger_ratio(
        self, handler: FSResourcesHandler, rom: Rom
    ):
        client = _CountingClient(_png_bytes(size=(600, 800)))

        await self._get_cover(handler, rom, False, client)

        cover_dir = self._cover_dir(handler, rom)
        assert self._image_size(cover_dir / "big.png") == (600, 800)
        assert self._image_size(cover_dir / "small.png") == (240, 320)

    async def test_fetches_a_collection_cover_once(self, handler: FSResourcesHandler):
        collection = Mock(spec=Collection)
        collection.id = 3
        collection.fs_resources_path = "collections/3"
        client = _CountingClient(_png_bytes())

        path_small, path_big = await self._get_cover(handler, collection, False, client)

        assert client.requests == [COVER_URL]
        assert path_small == "collections/3/cover/small.png"
        assert path_big == "collections/3/cover/big.png"
