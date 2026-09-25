import types
from pathlib import Path
from unittest.mock import Mock

import pytest

import adapters.services.sigil as sigil_adapter
from adapters.services.sigil import SigilExtractionResult, SigilService
from utils.platform_slugs import UniversalPlatformSlug as UPS


class FakeSigilError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def make_fake_sigil(extract: Mock) -> types.SimpleNamespace:
    return types.SimpleNamespace(extract=extract)


def make_result(
    title_id: str = "0100ABCD12340000",
    save_id: str = "0100ABCD12340000",
    usage: str = "folder-exact",
    switch_content_type: str | None = None,
    title_version: int | None = None,
) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        title_id=title_id,
        save_id=save_id,
        usage=usage,
        switch_content_type=switch_content_type,
        title_version=title_version,
    )


class TestExtractionEnabled:
    @pytest.mark.parametrize(
        "binding,skip,expected",
        [(True, False, True), (True, True, False), (False, False, False)],
    )
    def test_needs_the_binding_and_the_setting(
        self, monkeypatch, binding: bool, skip: bool, expected: bool
    ):
        monkeypatch.setattr(
            sigil_adapter, "sigil", make_fake_sigil(Mock()) if binding else None
        )
        monkeypatch.setattr(
            sigil_adapter.cm,
            "get_config",
            Mock(return_value=Mock(SKIP_TITLE_ID_EXTRACTION=skip)),
        )

        assert SigilService.extraction_enabled() is expected


class TestSigilService:
    @pytest.fixture
    def service(self):
        return SigilService()

    @pytest.mark.asyncio
    async def test_returns_none_when_binding_absent(
        self, service: SigilService, monkeypatch
    ):
        monkeypatch.setattr(sigil_adapter, "sigil", None)

        result = await service.extract_title_id(UPS.SWITCH, "/roms/switch/game.nsp")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_unsupported_platform(
        self, service: SigilService, monkeypatch
    ):
        extract = Mock(return_value=make_result())
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.N64, "/roms/n64/game.z64")

        assert result is None
        extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_extraction_maps_fields(
        self, service: SigilService, monkeypatch
    ):
        extract = Mock(
            return_value=make_result(
                title_id="0100ABCD12340000",
                save_id="0100ABCD12340000",
                usage="folder-exact",
            )
        )
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.SWITCH, "/roms/switch/game.nsp")

        assert result == SigilExtractionResult(
            title_id="0100ABCD12340000",
            save_target="0100ABCD12340000",
            usage="folder-exact",
        )

    @pytest.mark.asyncio
    # Version 0 is a real base-game version, not a missing one.
    @pytest.mark.parametrize(
        ("content_type", "version"), [("patch", 196608), ("application", 0)]
    )
    async def test_maps_switch_content_type_and_version(
        self,
        service: SigilService,
        monkeypatch,
        content_type: str,
        version: int,
    ):
        extract = Mock(
            return_value=make_result(
                switch_content_type=content_type,
                title_version=version,
            )
        )
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.SWITCH, "/roms/switch/game.nsp")

        assert result is not None
        assert result.content_type == content_type
        assert result.version == version

    @pytest.mark.asyncio
    @pytest.mark.parametrize("raw", ["unknown", "", None])
    async def test_absent_content_type_maps_to_none(
        self, service: SigilService, monkeypatch, raw: str | None
    ):
        extract = Mock(return_value=make_result(switch_content_type=raw))
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.SWITCH, "/roms/switch/game.nsp")

        assert result is not None
        assert result.content_type is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("code", ["NOT_FOUND", "UNSUPPORTED_FORMAT", "NEEDS_KEY"])
    async def test_routine_sigil_error_returns_none(
        self, service: SigilService, monkeypatch, code: str
    ):
        extract = Mock(side_effect=FakeSigilError(code))
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.PSX, "/roms/psx/game.bin")

        assert result is None

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_none(
        self, service: SigilService, monkeypatch
    ):
        extract = Mock(side_effect=OSError("native crash"))
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.PS2, "/roms/ps2/game.iso")

        assert result is None

    @pytest.mark.asyncio
    async def test_playlist_reads_its_first_disc(
        self, service: SigilService, monkeypatch, tmp_path: Path
    ):
        (tmp_path / "Game (Disc 1).chd").write_bytes(b"disc-1")
        (tmp_path / "Game (Disc 2).chd").write_bytes(b"disc-2")
        playlist = tmp_path / "Game.m3u"
        playlist.write_text("Game (Disc 1).chd\nGame (Disc 2).chd\n")
        extract = Mock(return_value=make_result(title_id="SLUS-21359"))
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.PS2, str(playlist))

        assert result is not None
        assert result.title_id == "SLUS-21359"
        extract.assert_called_once_with(
            str(tmp_path / "Game (Disc 1).chd"),
            platform="ps2",
            filename_fallback=False,
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "entry",
        [
            pytest.param("Game (Disc 1).chd", id="missing-disc"),
            pytest.param("Game.zip", id="archive-disc"),
            pytest.param("Game.tar.gz", id="tarball-disc"),
        ],
    )
    async def test_playlist_without_a_readable_disc_is_not_read(
        self, service: SigilService, monkeypatch, tmp_path: Path, entry: str
    ):
        (tmp_path / "Game.zip").write_bytes(b"archive")
        (tmp_path / "Game.tar.gz").write_bytes(b"archive")
        playlist = tmp_path / "Game.m3u"
        playlist.write_text(f"{entry}\n")
        extract = Mock(return_value=make_result())
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.PS2, str(playlist))

        assert result is None
        extract.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("platform_slug", [UPS.SWITCH, UPS.SWITCH_2])
    async def test_no_decryption_keys_are_passed(
        self, service: SigilService, monkeypatch, platform_slug: UPS
    ):
        """RomM never handles a user's console keys, so no key path is passed."""
        extract = Mock(return_value=make_result())
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        await service.extract_title_id(platform_slug, "/roms/switch/game.xci")

        extract.assert_called_once_with(
            "/roms/switch/game.xci",
            platform="switch",
            filename_fallback=False,
        )
