import types
from unittest.mock import Mock

import pytest

import adapters.services.sigil as sigil_adapter
from adapters.services.sigil import (
    SIGIL_PLATFORM_SLUGS,
    SigilExtractionResult,
    SigilService,
)
from handler.metadata.base_handler import UniversalPlatformSlug as UPS


class FakeSigilError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def make_fake_sigil(extract: Mock) -> types.SimpleNamespace:
    return types.SimpleNamespace(SigilError=FakeSigilError, extract=extract)


def make_result(
    title_id: str = "0100ABCD12340000",
    save_id: str = "0100ABCD12340000",
    usage: str = "folder-exact",
    switch_content_type: str | None = None,
    title_version: int | None = None,
) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        title_id=title_id,
        raw_serial="serial",
        save_id=save_id,
        platform="switch",
        source="binary",
        usage=usage,
        experimental=False,
        switch_content_type=switch_content_type,
        title_version=title_version,
    )


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
            save_id="0100ABCD12340000",
            usage="folder-exact",
        )

    @pytest.mark.asyncio
    async def test_maps_switch_content_type_and_version(
        self, service: SigilService, monkeypatch
    ):
        extract = Mock(
            return_value=make_result(
                switch_content_type="patch",
                title_version=196608,
            )
        )
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.SWITCH, "/roms/switch/game.nsp")

        assert result is not None
        assert result.content_type == "patch"
        assert result.version == 196608

    @pytest.mark.asyncio
    async def test_version_zero_is_preserved(self, service: SigilService, monkeypatch):
        extract = Mock(
            return_value=make_result(
                switch_content_type="application",
                title_version=0,
            )
        )
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.SWITCH, "/roms/switch/game.xci")

        assert result is not None
        assert result.content_type == "application"
        assert result.version == 0

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
    @pytest.mark.parametrize("platform_slug", [UPS.SWITCH, UPS.SWITCH_2])
    async def test_prod_keys_passed_for_switch_platforms(
        self, service: SigilService, monkeypatch, platform_slug: UPS
    ):
        extract = Mock(return_value=make_result())
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        await service.extract_title_id(
            platform_slug, "/roms/switch/game.xci", "/bios/switch/prod.keys"
        )

        extract.assert_called_once_with(
            "/roms/switch/game.xci",
            platform="switch",
            filename_fallback=False,
            prod_keys_path="/bios/switch/prod.keys",
        )

    @pytest.mark.asyncio
    async def test_prod_keys_not_passed_for_non_switch_platforms(
        self, service: SigilService, monkeypatch
    ):
        extract = Mock(return_value=make_result(usage="file-exact"))
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        await service.extract_title_id(
            UPS.PSP, "/roms/psp/game.iso", "/bios/switch/prod.keys"
        )

        extract.assert_called_once_with(
            "/roms/psp/game.iso",
            platform="psp",
            filename_fallback=False,
        )

    def test_platform_slug_mapping(self):
        assert SIGIL_PLATFORM_SLUGS[UPS.SWITCH_2] == "switch"
        assert SIGIL_PLATFORM_SLUGS[UPS.N3DS] == "3ds"
        assert SIGIL_PLATFORM_SLUGS[UPS.NGC] == "gamecube"
