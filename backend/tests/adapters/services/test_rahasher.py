import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from adapters.services.rahasher import (
    RAHASHER_VALID_HASH_REGEX,
    RAHasherError,
    RAHasherService,
)


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
    async def test_calculate_hash_success(self, service):
        """Test successful hash calculation."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1  # RAHasher returns 1 on success
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                result = await service.calculate_hash(7, "/path/to/game.nes")

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_proc.wait.assert_called_once()
        mock_proc.stdout.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_hash_rahasher_not_found(self, service):
        """Test when RAHasher executable is not found."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("RAHasher not found"),
        ):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                result = await service.calculate_hash(7, "/path/to/game.nes")

        assert result == ""

    @pytest.mark.asyncio
    async def test_calculate_hash_rahasher_failure(self, service):
        """Test when RAHasher fails with non-1 return code."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 2  # Error return code
        mock_proc.stderr.read.return_value = b"Error processing file"

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                result = await service.calculate_hash(7, "/path/to/game.nes")

        assert result == ""
        mock_proc.wait.assert_called_once()
        mock_proc.stderr.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_hash_no_stdout(self, service):
        """Test when RAHasher has no stdout."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout = None
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                result = await service.calculate_hash(7, "/path/to/game.nes")

        assert result == ""

    @pytest.mark.asyncio
    async def test_calculate_hash_empty_output(self, service):
        """Test when RAHasher returns empty output."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b""
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                result = await service.calculate_hash(7, "/path/to/game.nes")

        assert result == ""

    @pytest.mark.asyncio
    async def test_calculate_hash_invalid_hash_format(self, service):
        """Test when RAHasher returns invalid hash format."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b"invalid-hash-format\n"
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                result = await service.calculate_hash(7, "/path/to/game.nes")

        assert result == ""

    @pytest.mark.asyncio
    async def test_calculate_hash_with_extra_output(self, service):
        """Test when RAHasher returns hash with extra text."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = (
            b"Processing file... Hash: a1b2c3d4e5f6789012345678901234ab Done.\n"
        )
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                result = await service.calculate_hash(7, "/path/to/game.nes")

        assert result == "a1b2c3d4e5f6789012345678901234ab"

    @pytest.mark.asyncio
    async def test_calculate_hash_subprocess_args(self, service):
        """Test that subprocess is called with correct arguments."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subprocess:
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                await service.calculate_hash(7, "/path/to/game.nes")

        mock_subprocess.assert_called_once_with(
            "RAHasher",
            "7",
            "/path/to/game.nes",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @pytest.mark.asyncio
    async def test_calculate_hash_different_platforms(self, service):
        """Test hash calculation for different platforms."""
        test_cases = [
            (3, "/path/to/game.smc", "snes"),
            (1, "/path/to/game.md", "genesis"),
            (4, "/path/to/game.gb", "gb"),
        ]

        for platform_id, file_path, platform_slug in test_cases:
            mock_proc = AsyncMock()
            mock_proc.wait.return_value = 1
            mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
            mock_proc.stderr = None

            with patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_subprocess:
                with patch(
                    "handler.metadata.ra_handler.RA_ID_TO_SLUG",
                    {platform_id: platform_slug},
                ):
                    result = await service.calculate_hash(platform_id, file_path)

            assert result == "a1b2c3d4e5f6789012345678901234ab"
            mock_subprocess.assert_called_with(
                "RAHasher",
                str(platform_id),
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

    @pytest.mark.asyncio
    async def test_calculate_hash_stderr_handling(self, service):
        """Test proper handling of stderr when RAHasher fails."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 2
        mock_proc.stderr.read.return_value = b"File not supported"

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                result = await service.calculate_hash(7, "/path/to/game.nes")

        assert result == ""
        mock_proc.stderr.read.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_hash_stderr_none(self, service):
        """Test handling when stderr is None."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 2
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                result = await service.calculate_hash(7, "/path/to/game.nes")

        assert result == ""


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


# Integration-style tests (these would use real RAHasher if available)
class TestRAHasherServiceIntegration:
    """Integration tests for RAHasher service (requires RAHasher executable)."""

    @pytest.fixture
    def service(self):
        """Create a RAHasherService instance for integration testing."""
        return RAHasherService()

    @pytest.mark.asyncio
    @pytest.mark.skipif(True, reason="Requires RAHasher executable and test ROM files")
    async def test_calculate_hash_real_rahasher(self, service):
        """Test with real RAHasher executable (skipped by default)."""
        # This test would require:
        # 1. RAHasher executable in PATH
        # 2. A test ROM file
        # 3. Known expected hash for that ROM

        # Example (uncomment and modify for real testing):
        # result = await service.calculate_hash(7, "/path/to/test.nes")
        # assert result == "expected_hash_value"
        pass


# Performance tests
class TestRAHasherServicePerformance:
    """Performance tests for RAHasher service."""

    @pytest.fixture
    def service(self):
        """Create a RAHasherService instance for performance testing."""
        return RAHasherService()

    @pytest.mark.asyncio
    async def test_concurrent_hash_calculations(self, service):
        """Test multiple concurrent hash calculations."""
        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with patch("handler.metadata.ra_handler.RA_ID_TO_SLUG", {7: "nes"}):
                # Run 5 concurrent hash calculations
                tasks = [
                    service.calculate_hash(7, f"/path/to/game{i}.nes") for i in range(5)
                ]
                results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(result == "a1b2c3d4e5f6789012345678901234ab" for result in results)
        assert len(results) == 5
