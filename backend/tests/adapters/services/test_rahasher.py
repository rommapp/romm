import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from adapters.services.rahasher import (
    PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID,
    RA_BUFFER_HASH_UNSUPPORTED,
    RAHASHER_VALID_HASH_REGEX,
    RAHasherError,
    RAHasherService,
    _first_m3u_entry,
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


class TestFirstM3uEntry:
    """Unit tests for resolving an .m3u playlist to its first disc file,
    mirroring RAHasher's own playlist handling (it hashes the first entry)."""

    def test_returns_first_entry_relative_to_playlist_folder(self, tmp_path):
        disc1 = tmp_path / "game (Disc 1).rvz"
        disc1.write_bytes(b"x" * 100)
        (tmp_path / "game (Disc 2).rvz").write_bytes(b"x" * 100)
        m3u = tmp_path / "game.m3u"
        m3u.write_text("game (Disc 1).rvz\ngame (Disc 2).rvz\n")

        assert _first_m3u_entry(m3u) == disc1

    def test_skips_comments_and_blank_lines(self, tmp_path):
        disc = tmp_path / "disc.cue"
        disc.write_bytes(b"x" * 10)
        m3u = tmp_path / "game.m3u"
        m3u.write_text("#EXTM3U\n\n# a comment\ndisc.cue\n")

        assert _first_m3u_entry(m3u) == disc

    def test_handles_utf8_bom_and_crlf(self, tmp_path):
        disc = tmp_path / "disc.rvz"
        disc.write_bytes(b"x" * 10)
        m3u = tmp_path / "game.m3u"
        m3u.write_bytes(b"\xef\xbb\xbfdisc.rvz\r\n")

        assert _first_m3u_entry(m3u) == disc

    def test_resolves_absolute_entry_as_is(self, tmp_path):
        disc = tmp_path / "elsewhere" / "disc.rvz"
        disc.parent.mkdir()
        disc.write_bytes(b"x" * 10)
        m3u = tmp_path / "game.m3u"
        m3u.write_text(f"{disc}\n")

        assert _first_m3u_entry(m3u) == disc

    def test_returns_none_when_first_entry_missing(self, tmp_path):
        """Only the first entry counts (RAHasher hashes the first disc);
        a dangling first entry means the playlist can't be resolved."""
        (tmp_path / "game (Disc 2).rvz").write_bytes(b"x" * 10)
        m3u = tmp_path / "game.m3u"
        m3u.write_text("game (Disc 1).rvz\ngame (Disc 2).rvz\n")

        assert _first_m3u_entry(m3u) is None

    def test_returns_none_for_unreadable_playlist(self, tmp_path):
        assert _first_m3u_entry(tmp_path / "missing.m3u") is None

    def test_returns_none_for_empty_playlist(self, tmp_path):
        m3u = tmp_path / "game.m3u"
        m3u.write_text("#EXTM3U\n\n")

        assert _first_m3u_entry(m3u) is None


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


class TestRAHasherRvzNativeHashing:
    """GameCube and Wii .rvz/.wia disc images are hashed natively instead of
    being handed to RAHasher, which can't read the RVZ container
    (issues #3649 and #3650)."""

    @pytest.fixture
    def service(self):
        return RAHasherService()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ext", [".rvz", ".wia"])
    @pytest.mark.parametrize(
        "ups,slug,native_fn",
        [
            (UPS.NGC, "ngc", "calculate_gamecube_ra_hash"),
            (UPS.WII, "wii", "calculate_wii_ra_hash"),
        ],
    )
    async def test_native_hash_short_circuits_rahasher(
        self, service: RAHasherService, ups, slug, native_fn, ext
    ):
        """A successful native hash returns without spawning RAHasher."""
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[ups]

        with (
            patch(
                f"adapters.services.rahasher.{native_fn}",
                return_value="a1b2c3d4e5f6789012345678901234ab",
            ) as mock_native,
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": platform_id, "slug": slug}, f"/roms/{slug}/game{ext}"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_native.assert_called_once_with(f"/roms/{slug}/game{ext}")
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "ups,slug,native_fn",
        [
            (UPS.NGC, "ngc", "calculate_gamecube_ra_hash"),
            (UPS.WII, "wii", "calculate_wii_ra_hash"),
        ],
    )
    async def test_folder_glob_without_descriptor_hashes_largest_rvz_natively(
        self, service: RAHasherService, tmp_path, ups, slug, native_fn
    ):
        """A disc folder with no .cue/.gdi/.m3u falls back to the largest
        file; when that is an .rvz it must reach the native hasher."""
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[ups]
        (tmp_path / "game (Disc 1).rvz").write_bytes(b"x" * 200)
        disc2 = tmp_path / "game (Disc 2).rvz"
        disc2.write_bytes(b"x" * 300)

        with (
            patch(
                f"adapters.services.rahasher.{native_fn}",
                return_value="a1b2c3d4e5f6789012345678901234ab",
            ) as mock_native,
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": platform_id, "slug": slug}, f"{tmp_path}/*"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_native.assert_called_once_with(str(disc2))
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_rahasher_when_native_fails(
        self, service: RAHasherService
    ):
        """If native hashing returns nothing, RAHasher is still attempted."""
        ngc_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.NGC]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with (
            patch(
                "adapters.services.rahasher.calculate_gamecube_ra_hash",
                return_value="",
            ) as mock_native,
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": ngc_id, "slug": "ngc"}, "/roms/ngc/game.rvz"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_native.assert_called_once()
        mock_subprocess.assert_called_once()

    @pytest.mark.asyncio
    async def test_native_hashing_skipped_for_other_platforms(
        self, service: RAHasherService
    ):
        """An .rvz on a non-GameCube/Wii platform must not hash natively."""
        psx_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSX]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with (
            patch(
                "adapters.services.rahasher.calculate_gamecube_ra_hash"
            ) as mock_gc_native,
            patch(
                "adapters.services.rahasher.calculate_wii_ra_hash"
            ) as mock_wii_native,
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            await service.calculate_hash(
                {"ra_id": psx_id, "slug": "psx"}, "/roms/psx/game.rvz"
            )

        mock_gc_native.assert_not_called()
        mock_wii_native.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("ups,slug", [(UPS.NGC, "ngc"), (UPS.WII, "wii")])
    async def test_native_hashing_skipped_for_raw_iso(
        self, service: RAHasherService, ups, slug
    ):
        """Plain .iso discs still go to RAHasher (it reads them fine)."""
        platform_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[ups]

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with (
            patch(
                "adapters.services.rahasher.calculate_gamecube_ra_hash"
            ) as mock_gc_native,
            patch(
                "adapters.services.rahasher.calculate_wii_ra_hash"
            ) as mock_wii_native,
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_subprocess,
        ):
            await service.calculate_hash(
                {"ra_id": platform_id, "slug": slug}, f"/roms/{slug}/game.iso"
            )

        mock_gc_native.assert_not_called()
        mock_wii_native.assert_not_called()
        mock_subprocess.assert_called_once()


class TestRAHasherM3uNativeResolution:
    """Folder-based multi-disc ROMs resolve to their .m3u playlist, but RAHasher
    can only follow a playlist to formats it can read. Playlists pointing at
    natively-hashed containers (RVZ/WIA, PSP compressed ISOs) must resolve to
    the first disc so the native hashers see it (issue #3797)."""

    @pytest.fixture
    def service(self):
        return RAHasherService()

    def _make_ngc_folder(self, tmp_path):
        """The exact layout from issue #3797: two .rvz discs plus an .m3u."""
        disc1 = tmp_path / "Tales of Symphonia (Usa) (Disc 1).rvz"
        disc1.write_bytes(b"x" * 200)
        (tmp_path / "Tales of Symphonia (Usa) (Disc 2).rvz").write_bytes(b"x" * 300)
        m3u = tmp_path / "Tales of Symphonia (Usa).m3u"
        m3u.write_text(
            "Tales of Symphonia (Usa) (Disc 1).rvz\n"
            "Tales of Symphonia (Usa) (Disc 2).rvz\n"
        )
        return disc1

    @pytest.mark.asyncio
    async def test_ngc_folder_with_m3u_hashes_first_disc_natively(
        self, service: RAHasherService, tmp_path
    ):
        """The folder glob resolves to the .m3u, which must then resolve to
        disc 1 and short-circuit into the native GameCube hasher."""
        ngc_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.NGC]
        disc1 = self._make_ngc_folder(tmp_path)

        with (
            patch(
                "adapters.services.rahasher.calculate_gamecube_ra_hash",
                return_value="a1b2c3d4e5f6789012345678901234ab",
            ) as mock_native,
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": ngc_id, "slug": "ngc"}, f"{tmp_path}/*"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_native.assert_called_once_with(str(disc1))
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_wii_folder_with_m3u_hashes_first_disc_natively(
        self, service: RAHasherService, tmp_path
    ):
        wii_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.WII]
        disc1 = tmp_path / "game (Disc 1).wia"
        disc1.write_bytes(b"x" * 200)
        (tmp_path / "game (Disc 2).wia").write_bytes(b"x" * 300)
        (tmp_path / "game.m3u").write_text("game (Disc 1).wia\ngame (Disc 2).wia\n")

        with (
            patch(
                "adapters.services.rahasher.calculate_wii_ra_hash",
                return_value="a1b2c3d4e5f6789012345678901234ab",
            ) as mock_native,
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": wii_id, "slug": "wii"}, f"{tmp_path}/*"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_native.assert_called_once_with(str(disc1))
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_direct_m3u_file_resolves_to_native_disc(
        self, service: RAHasherService, tmp_path
    ):
        """A standalone .m3u scanned as a single-file ROM must resolve the
        same way as the folder-glob path."""
        ngc_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.NGC]
        disc1 = self._make_ngc_folder(tmp_path)

        with (
            patch(
                "adapters.services.rahasher.calculate_gamecube_ra_hash",
                return_value="a1b2c3d4e5f6789012345678901234ab",
            ) as mock_native,
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": ngc_id, "slug": "ngc"},
                str(tmp_path / "Tales of Symphonia (Usa).m3u"),
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_native.assert_called_once_with(str(disc1))
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_psp_m3u_resolves_to_native_container(
        self, service: RAHasherService, tmp_path
    ):
        psp_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSP]
        disc1 = tmp_path / "game (Disc 1).cso"
        disc1.write_bytes(b"x" * 200)
        (tmp_path / "game (Disc 2).cso").write_bytes(b"x" * 300)
        (tmp_path / "game.m3u").write_text("game (Disc 1).cso\ngame (Disc 2).cso\n")

        with (
            patch(
                "adapters.services.rahasher.calculate_psp_ra_hash",
                return_value="a1b2c3d4e5f6789012345678901234ab",
            ) as mock_native,
            patch("asyncio.create_subprocess_exec") as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": psp_id, "slug": "psp"}, f"{tmp_path}/*"
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        mock_native.assert_called_once_with(str(disc1))
        mock_subprocess.assert_not_called()

    @pytest.mark.asyncio
    async def test_m3u_of_cue_discs_still_goes_to_rahasher(
        self, service: RAHasherService, tmp_path
    ):
        """Playlists of formats RAHasher reads (bin/cue) keep their current
        behavior: the .m3u itself is handed to RAHasher."""
        psx_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSX]
        (tmp_path / "game (Disc 1).bin").write_bytes(b"x" * 5000)
        (tmp_path / "game (Disc 1).cue").write_bytes(b"x" * 50)
        (tmp_path / "game (Disc 2).bin").write_bytes(b"x" * 5000)
        (tmp_path / "game (Disc 2).cue").write_bytes(b"x" * 50)
        m3u = tmp_path / "game.m3u"
        m3u.write_text("game (Disc 1).cue\ngame (Disc 2).cue\n")

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 0
        mock_proc.stdout.read.return_value = b"a1b2c3d4e5f6789012345678901234ab\n"
        mock_proc.stderr = None

        with patch(
            "asyncio.create_subprocess_exec", return_value=mock_proc
        ) as mock_subprocess:
            result = await service.calculate_hash(
                {"ra_id": psx_id, "slug": "psx"}, str(m3u)
            )

        assert result == "a1b2c3d4e5f6789012345678901234ab"
        call_args = mock_subprocess.call_args[0]
        assert str(m3u) in call_args

    @pytest.mark.asyncio
    async def test_rvz_m3u_on_other_platform_keeps_playlist(
        self, service: RAHasherService, tmp_path
    ):
        """An .rvz playlist on a non-GameCube/Wii platform must not trigger
        native resolution; behavior is unchanged."""
        psx_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.PSX]
        (tmp_path / "game.rvz").write_bytes(b"x" * 200)
        m3u = tmp_path / "game.m3u"
        m3u.write_text("game.rvz\n")

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b""
        mock_proc.stderr.read.return_value = b"Could not open track"

        with (
            patch(
                "adapters.services.rahasher.calculate_gamecube_ra_hash"
            ) as mock_gc_native,
            patch(
                "adapters.services.rahasher.calculate_wii_ra_hash"
            ) as mock_wii_native,
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": psx_id, "slug": "psx"}, str(m3u)
            )

        assert result == ""
        mock_gc_native.assert_not_called()
        mock_wii_native.assert_not_called()
        call_args = mock_subprocess.call_args[0]
        assert str(m3u) in call_args

    @pytest.mark.asyncio
    async def test_dangling_m3u_falls_through_to_rahasher(
        self, service: RAHasherService, tmp_path
    ):
        """A playlist whose first entry is missing on disk keeps the .m3u
        path and falls through to RAHasher without crashing."""
        ngc_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.NGC]
        m3u = tmp_path / "game.m3u"
        m3u.write_text("game (Disc 1).rvz\n")

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b""
        mock_proc.stderr.read.return_value = b"Could not open file"

        with (
            patch(
                "adapters.services.rahasher.calculate_gamecube_ra_hash"
            ) as mock_native,
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": ngc_id, "slug": "ngc"}, f"{tmp_path}/*"
            )

        assert result == ""
        mock_native.assert_not_called()
        call_args = mock_subprocess.call_args[0]
        assert str(m3u) in call_args

    @pytest.mark.asyncio
    async def test_native_failure_falls_back_to_rahasher_with_disc(
        self, service: RAHasherService, tmp_path
    ):
        """If the native hasher can't parse the resolved disc, RAHasher is
        still attempted with the disc file (no worse than before)."""
        ngc_id = PLATFORM_SLUG_TO_RETROACHIEVEMENTS_ID[UPS.NGC]
        disc1 = self._make_ngc_folder(tmp_path)

        mock_proc = AsyncMock()
        mock_proc.wait.return_value = 1
        mock_proc.stdout.read.return_value = b""
        mock_proc.stderr.read.return_value = b"Not a Gamecube disc"

        with (
            patch(
                "adapters.services.rahasher.calculate_gamecube_ra_hash",
                return_value="",
            ) as mock_native,
            patch(
                "asyncio.create_subprocess_exec", return_value=mock_proc
            ) as mock_subprocess,
        ):
            result = await service.calculate_hash(
                {"ra_id": ngc_id, "slug": "ngc"}, f"{tmp_path}/*"
            )

        assert result == ""
        mock_native.assert_called_once_with(str(disc1))
        call_args = mock_subprocess.call_args[0]
        assert str(disc1) in call_args


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
