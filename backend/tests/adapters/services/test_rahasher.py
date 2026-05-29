import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from adapters.services.rahasher import (
    PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID,
    RA_BUFFER_HASH_UNSUPPORTED,
    RAHASHER_VALID_HASH_REGEX,
    RAHasherError,
    RAHasherService,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS


class TestRAHasherValidHashRegex:
    """Test the hash validation regex."""

    def test_valid_hash_regex_matches_valid_hash(self):
        """Test that valid 32-character hex hashes match the regex."""
        valid_hashes = [
            "a1b2c3d4e5f6789012345678901234ab",
            "0123456789abcdef0123456789abcdef",
            "ffffffffffffffffffffffffffffffff",
            "00000000000000000000000000000000",
        ]

        for hash_value in valid_hashes:
            assert RAHASHER_VALID_HASH_REGEX.search(hash_value) is not None

    def test_valid_hash_regex_rejects_invalid_hash(self):
        """Test that invalid hashes don't match the regex."""
        invalid_hashes = [
            "a1b2c3d4e5f6789012345678901234",  # Too short
            "g1b2c3d4e5f6789012345678901234ab",  # Invalid character
            "A1B2C3D4E5F6789012345678901234AB",  # Uppercase
            "",  # Empty
            "not-a-hash",  # Not hex
        ]

        for hash_value in invalid_hashes:
            assert RAHASHER_VALID_HASH_REGEX.search(hash_value) is None


class TestRAHasherService:
    """Test the RAHasher service."""

    @pytest.fixture
    def service(self):
        """Create a RAHasherService instance for testing."""
        return RAHasherService()

    @pytest.mark.asyncio
    async def test_calculate_hash_success(self, service: RAHasherService):
        """Test successful hash calculation."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0  # RAHasher returns 0 on success
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_proc.wait.assert_called_once()
        mock_proc.stdout.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_hash_rahasher_not_found(self, service: RAHasherService):
        """Test when RAHasher executable is not found."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("RAHasher not found"),
        ):
            result = await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        assert result == ""

    @pytest.mark.asyncio
    async def test_calculate_hash_rahasher_failure(self, service: RAHasherService):
        """Test when RAHasher fails with non-1 return code."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 2  # Error return code
        mock_proc.stderr.read.return_value = b"Error processing file"

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        assert result == ""
        mock_proc.wait.assert_called_once()
        mock_proc.stderr.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_hash_no_stdout(self, service: RAHasherService):
        """Test when RAHasher has no stdout."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout = None
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        assert result == ""

    @pytest.mark.asyncio
    async def test_calculate_hash_empty_output(self, service: RAHasherService):
        """Test when RAHasher returns empty output."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b""
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        assert result == ""

    @pytest.mark.asyncio
    async def test_calculate_hash_invalid_hash_format(self, service: RAHasherService):
        """Test when RAHasher returns invalid hash format."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b"invalid-hash-format\n"
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        assert result == ""

    @pytest.mark.asyncio
    async def test_calculate_hash_with_extra_output(self, service: RAHasherService):
        """Test when RAHasher returns hash with extra text."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = (
            b"Processing file... Hash: a1b2c3d4e5f6789012345678901234ab Done.\n"
        )
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"

    @pytest.mark.asyncio
    async def test_calculate_hash_subprocess_args(self, service: RAHasherService):
        """Test that subprocess is called with correct arguments."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subprocess:
            await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        mock_subprocess.assert_called_once_with(
            "RAHasher",
            "7",
            "/path/to/game.nes",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @pytest.mark.asyncio
    async def test_calculate_hash_different_platforms(self, service: RAHasherService):
        """Test hash calculation for different platforms."""
        test_cases = [
            (3, "/path/to/game.smc", "snes"),
            (1, "/path/to/game.md", "genesis"),
            (4, "/path/to/game.gb", "gb"),
        ]

        for platform_id, file_path, platform_slug in test_cases:
            mock_proc = AsyncMock()
            mock_proc.wait.return_value = 0
            mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
            mock_proc.stderr = None

            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_subprocess:
                result = await service.calculate_hash(
                    {"ra_id": platform_id, "slug": platform_slug},
                    file_path,
                )

            assert result == "a1b2c3d4e5f6789012345678901234ab"
            mock_subprocess.assert_called_with(
                "RAHasher",
                str(platform_id),
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

    @pytest.mark.asyncio
    async def test_calculate_hash_stderr_handling(self, service: RAHasherService):
        """Test proper handling of stderr when RAHasher fails."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 2
        mock_proc.stderr.read.return_value = b"File not supported"

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        assert result == ""
        mock_proc.stderr.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_hash_stderr_none(self, service: RAHasherService):
        """Test handling when stderr is None."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 2
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.calculate_hash(
                {"ra_id": 7, "slug": "nes"}, "/path/to/game.nes"
            )

        assert result == ""


class TestRAHasherArchiveSkip:
    """Verify RAHasher is skipped when an archive is fed to a disc-based platform."""

    @pytest.fixture
    def service(self):
        return RAHasherService()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "ups,ext",
        [
            (UPS.PSP, ".zip"),
            (UPS.PS2, ".7z"),
            (UPS.PSX, ".tar"),
            (UPS.SATURN, ".gz"),
            (UPS.DC, ".bz2"),
            (UPS.WII, ".rar"),
        ],
    )
    async def test_skips_subprocess_for_archive_on_disc_platform(
        self, service: RAHasherService, ups, ext
    ):
        """No subprocess should be spawned; calculate_hash returns '' immediately."""
        assert ups in RA_BUFFER_HASH_UNSUPPORTED
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[ups]

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            result = await service.calculate_hash(
                {"ra_id": platform_id, "slug": "disc-platform"},
                f"/path/to/game{ext}",
            )

        assert result == ""
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_skip_archive_for_cartridge_platform(
        self, service: RAHasherService
    ):
        """Cartridge platforms (e.g. NES) support buffer hash; don't skip."""
        assert UPS.NES not in RA_BUFFER_HASH_UNSUPPORTED
        nes_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.NES]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subprocess:
            result = await service.calculate_hash(
                {"ra_id": nes_id, "slug": "nes"}, "/path/to/game.zip"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_wildcard_folder_with_archives_on_disc_platform(
        self, service: RAHasherService, tmp_path
    ):
        """Folder-based ROM whose directory contains compressed files must be
        skipped for disc-based platforms — same as a single archive file."""
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSX]
        (tmp_path / "disc1.zip").write_bytes(b"fake")
        (tmp_path / "disc2.zip").write_bytes(b"fake")

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            result = await service.calculate_hash(
                {"ra_id": platform_id, "slug": "psx"},
                f"{tmp_path}/*",
            )

        assert result == ""
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_skip_wildcard_folder_without_archives_on_disc_platform(
        self, service: RAHasherService, tmp_path
    ):
        """Folder-based ROM with only raw disc images must still go through RAHasher."""
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSX]
        (tmp_path / "disc1.bin").write_bytes(b"fake")
        (tmp_path / "disc1.cue").write_bytes(b"fake")

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subprocess:
            result = await service.calculate_hash(
                {"ra_id": platform_id, "slug": "psx"},
                f"{tmp_path}/*",
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_cartridge_platform_folder_with_archives_hashes_largest(
        self, service: RAHasherService, tmp_path
    ):
        """Cartridge platforms: folder with archives should hash the largest archive directly."""
        assert UPS.GBA not in RA_BUFFER_HASH_UNSUPPORTED
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.GBA]
        small = tmp_path / "small.zip"
        large = tmp_path / "large.zip"
        small.write_bytes(b"s" * 100)
        large.write_bytes(b"l" * 500)

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subprocess:
            result = await service.calculate_hash(
                {"ra_id": platform_id, "slug": "gba"},
                f"{tmp_path}/*",
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_subprocess.assert_called_once()
        # RAHasher must be called with the largest archive path, not the glob
        call_args = mock_subprocess.call_args[0]
        assert str(large) in call_args

    @pytest.mark.asyncio
    async def test_does_not_skip_raw_iso_for_disc_platform(
        self, service: RAHasherService
    ):
        """Raw disc images must still go through RAHasher for disc platforms."""
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSP]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subprocess:
            result = await service.calculate_hash(
                {"ra_id": platform_id, "slug": "psp"}, "/path/to/game.iso"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_subprocess.assert_called_once()


class TestRAHasherError:
    """Test the RAHasherError exception."""

    def test_rahasher_error_is_exception(self):
        """Test that RAHasherError is an Exception."""
        assert issubclass(RAHasherError, Exception)

    def test_rahasher_error_can_be_raised(self):
        """Test that RAHasherError can be raised and caught."""
        with pytest.raises(RAHasherError):
            raise RAHasherError("Test error")

    def test_rahasher_error_with_message(self):
        """Test that RAHasherError can carry a message."""
        message = "Hash calculation failed"
        try:
            raise RAHasherError(message)
        except RAHasherError as e:
            assert str(e) == message


# Performance tests
class TestRAHasherServicePerformance:
    """Performance tests for RAHasher service."""

    @pytest.fixture
    def service(self):
        """Create a RAHasherService instance for performance testing."""
        return RAHasherService()

    @pytest.mark.asyncio
    async def test_concurrent_hash_calculations(self, service: RAHasherService):
        """Test multiple concurrent hash calculations."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            # Run 5 concurrent hash calculations
            tasks = [
                service.calculate_hash(
                    {"ra_id": 7, "slug": "nes"}, f"/path/to/game{i}.nes"
                )
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(result == "a1b2c3d4e5f6789012345678901234ab" for result in results)
        assert len(results) == 5
