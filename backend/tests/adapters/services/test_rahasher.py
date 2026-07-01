import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from adapters.services.rahasher import (
    PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID,
    RA_BUFFER_HASH_UNSUPPORTED,
    RAHASHER_VALID_HASH_REGEX,
    RAHasherError,
    RAHasherService,
    _pick_ra_file,
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
        """Folder-based ROM with only raw disc images must still go through RAHasher,
        handed the real descriptor file rather than the unexpanded glob."""
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSX]
        (tmp_path / "disc1.bin").write_bytes(b"fake")
        cue = tmp_path / "disc1.cue"
        cue.write_bytes(b"fake")

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
        # RAHasher must be handed the .cue descriptor, never the literal "/*"
        call_args = mock_subprocess.call_args[0]
        assert str(cue) in call_args
        assert not any(str(a).endswith("/*") for a in call_args)

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


class TestPickRAFile:
    """Unit tests for picking a single real file to hand RAHasher for a
    folder-based ROM (the standard Redump .cue + .bin layout, .gdi sets, etc.)."""

    def test_returns_none_for_missing_folder(self, tmp_path):
        assert _pick_ra_file(tmp_path / "does-not-exist") is None

    def test_returns_none_for_empty_folder(self, tmp_path):
        assert _pick_ra_file(tmp_path) is None

    def test_prefers_cue_over_bin(self, tmp_path):
        """A bin/cue disc: hand RAHasher the .cue, which references the tracks."""
        (tmp_path / "game.bin").write_bytes(b"x" * 5000)
        cue = tmp_path / "game.cue"
        cue.write_bytes(b"x" * 50)

        assert _pick_ra_file(tmp_path) == cue

    def test_prefers_cue_for_multi_bin_disc(self, tmp_path):
        """Multi-track disc with several .bin files and one .cue → the .cue."""
        for i in range(1, 4):
            (tmp_path / f"game (Track {i}).bin").write_bytes(b"x" * (1000 * i))
        cue = tmp_path / "game.cue"
        cue.write_bytes(b"x" * 80)

        assert _pick_ra_file(tmp_path) == cue

    def test_prefers_gdi_for_dreamcast(self, tmp_path):
        """Dreamcast GD-ROM: the .gdi descriptor points at the track files."""
        (tmp_path / "track01.bin").write_bytes(b"x" * 4000)
        (tmp_path / "track02.raw").write_bytes(b"x" * 9000)
        gdi = tmp_path / "game.gdi"
        gdi.write_bytes(b"x" * 60)

        assert _pick_ra_file(tmp_path) == gdi

    def test_picks_m3u_when_only_descriptor(self, tmp_path):
        """A folder whose only descriptor is an .m3u playlist resolves to it."""
        (tmp_path / "data.bin").write_bytes(b"x" * 4000)
        m3u = tmp_path / "game.m3u"
        m3u.write_bytes(b"disc.cue\n")

        assert _pick_ra_file(tmp_path) == m3u

    def test_cue_wins_over_m3u(self, tmp_path):
        """When both a .cue and an .m3u exist, the per-disc .cue is preferred."""
        m3u = tmp_path / "game.m3u"
        m3u.write_bytes(b"x" * 4000)
        cue = tmp_path / "game.cue"
        cue.write_bytes(b"x" * 50)

        assert _pick_ra_file(tmp_path) == cue

    def test_falls_back_to_largest_file_without_descriptor(self, tmp_path):
        """No descriptor (e.g. raw .iso, or a multi-file cartridge set): the
        largest file is the best single-file guess."""
        (tmp_path / "small.dat").write_bytes(b"x" * 100)
        big = tmp_path / "game.iso"
        big.write_bytes(b"x" * 9000)

        assert _pick_ra_file(tmp_path) == big

    def test_descriptor_match_is_case_insensitive(self, tmp_path):
        (tmp_path / "game.bin").write_bytes(b"x" * 5000)
        cue = tmp_path / "GAME.CUE"
        cue.write_bytes(b"x" * 50)

        assert _pick_ra_file(tmp_path) == cue

    def test_ignores_subdirectories(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        cue = tmp_path / "game.cue"
        cue.write_bytes(b"x" * 50)

        assert _pick_ra_file(tmp_path) == cue


class TestRAHasherWildcardFolderResolution:
    """Folder-based disc ROMs (.cue + .bin) must resolve the "/*" glob to a real
    descriptor file before spawning RAHasher — it is launched without a shell,
    so it never expands the glob itself (GitHub issue #3497)."""

    @pytest.fixture
    def service(self):
        return RAHasherService()

    @pytest.mark.asyncio
    async def test_resolves_glob_to_cue_descriptor(
        self, service: RAHasherService, tmp_path
    ):
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSX]
        (tmp_path / "game.bin").write_bytes(b"x" * 5000)
        cue = tmp_path / "game.cue"
        cue.write_bytes(b"x" * 50)

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"8c8db8c41e2a4c7d0ef7fc1c2f74ef7a\n"
        mock_proc.stderr = None

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subprocess:
            result = await service.calculate_hash(
                {"ra_id": platform_id, "slug": "psx"},
                f"{tmp_path}/*",
            )

        assert result == "8c8db8c41e2a4c7d0ef7fc1c2f74ef7a"
        mock_subprocess.assert_called_once_with(
            "RAHasher",
            str(platform_id),
            str(cue),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @pytest.mark.asyncio
    async def test_resolves_glob_to_largest_file_without_descriptor(
        self, service: RAHasherService, tmp_path
    ):
        """Folder-stored cartridge set / raw image with no descriptor: hand
        RAHasher the largest single file rather than the unexpanded glob."""
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.GBA]
        (tmp_path / "small.dat").write_bytes(b"x" * 100)
        big = tmp_path / "game.gba"
        big.write_bytes(b"x" * 9000)

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
        call_args = mock_subprocess.call_args[0]
        assert str(big) in call_args
        assert not any(str(a).endswith("/*") for a in call_args)

    @pytest.mark.asyncio
    async def test_unresolvable_empty_folder_does_not_crash(
        self, service: RAHasherService, tmp_path
    ):
        """An empty/unresolvable folder leaves the glob untouched (nothing to
        hash) and still returns gracefully."""
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSX]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b""
        mock_proc.stderr.read.return_value = b"Could not open track"

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await service.calculate_hash(
                {"ra_id": platform_id, "slug": "psx"},
                f"{tmp_path}/*",
            )

        assert result == ""


class TestRAHasherPspNativeHashing:
    """PSP compressed-ISO containers (.cso/.ciso/.zso/.dax) are hashed natively
    instead of being handed to RAHasher, which can't read them (issue #3600)."""

    @pytest.fixture
    def service(self):
        return RAHasherService()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ext", [".cso", ".ciso", ".zso", ".dax"])
    async def test_native_hash_short_circuits_rahasher(
        self, service: RAHasherService, ext
    ):
        """A successful native hash returns without spawning RAHasher."""
        psp_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSP]

        with (
            patch(
                "adapters.services.rahasher.calculate_psp_ra_hash",
                return_value="a1b2c3d4e5f6789012345678901234ab",
            ) as mock_native,
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": psp_id, "slug": "psp"}, f"/roms/psp/game{ext}"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_native.assert_called_once_with(f"/roms/psp/game{ext}")
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_rahasher_when_native_fails(
        self, service: RAHasherService
    ):
        """If native hashing returns nothing, RAHasher is still attempted."""
        psp_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSP]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with (
            patch(
                "adapters.services.rahasher.calculate_psp_ra_hash",
                return_value="",
            ) as mock_native,
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": psp_id, "slug": "psp"}, "/roms/psp/game.cso"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_native.assert_called_once()
        mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_native_hashing_skipped_for_non_psp_platform(
        self, service: RAHasherService
    ):
        """A .cso on a non-PSP platform must not trigger native PSP hashing."""
        psx_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSX]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with (
            patch("adapters.services.rahasher.calculate_psp_ra_hash") as mock_native,
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            await service.calculate_hash(
                {"ra_id": psx_id, "slug": "psx"}, "/roms/psx/game.cso"
            )

        mock_native.assert_not_called()

    @pytest.mark.asyncio
    async def test_native_hashing_skipped_for_raw_iso(self, service: RAHasherService):
        """Plain .iso PSP discs still go to RAHasher (it reads them fine)."""
        psp_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSP]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with (
            patch("adapters.services.rahasher.calculate_psp_ra_hash") as mock_native,
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_subprocess,
        ):
            await service.calculate_hash(
                {"ra_id": psp_id, "slug": "psp"}, "/roms/psp/game.iso"
            )

        mock_native.assert_not_called()
        mock_subprocess.assert_called_once()


class TestRAHasherFDSPlatformMapping:
    """The Famicom Disk System is its own RetroAchievements console (ID 81), not
    grouped under NES/Famicom (ID 7). The fds slug must be present in the
    slug->RA-id table and treated as a buffer-hashable platform, since .fds disk
    images are hashed in-buffer rather than as CD/ISO discs (GitHub issue
    #3646)."""

    @pytest.fixture
    def service(self):
        return RAHasherService()

    def test_fds_slug_maps_to_console_81(self):
        assert PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.FDS] == 81

    def test_fds_console_is_distinct_from_nes(self):
        # RA lists the FDS as a separate console, so it must not reuse the
        # NES/Famicom console ID (7).
        assert (
            PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.FDS]
            != PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.NES]
        )

    def test_fds_is_buffer_hashable(self):
        # .fds disk images are buffer-hashable, so FDS must not be treated as
        # disc-based (which would skip RAHasher for archived ROMs).
        assert UPS.FDS not in RA_BUFFER_HASH_UNSUPPORTED

    @pytest.mark.asyncio
    async def test_calculate_hash_runs_rahasher_for_fds(self, service: RAHasherService):
        """An FDS disk image must actually reach RAHasher (issue #3646)."""
        fds_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.FDS]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subprocess:
            result = await service.calculate_hash(
                {"ra_id": fds_id, "slug": "fds"}, "/roms/fds/game.fds"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_subprocess.assert_called_once_with(
            "RAHasher",
            str(fds_id),
            "/roms/fds/game.fds",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )


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
