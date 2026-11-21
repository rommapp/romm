from pathlib import Path

import pytest
from tests.utils.nup_builder import (
    KIND_ADDON,
    KIND_ADDON_UPDATE,
    KIND_BASE,
    KIND_SYSTEM,
    KIND_UPDATE,
    Pkg,
    build_nup,
)

import adapters.services.nup as nup_adapter
from adapters.services.nup import NupService
from adapters.services.sigil import SigilExtractionResult
from utils.nup import FLAG_STANDALONE_UPDATE
from utils.platform_slugs import UniversalPlatformSlug as UPS

S1_BASE = 0x0100ABCD12340000
S2_BASE = 0x040074A01BF12000


def write(tmp_path: Path, data: bytes) -> str:
    path = tmp_path / "game.nup"
    path.write_bytes(data)
    return str(path)


@pytest.fixture
def service() -> NupService:
    return NupService()


class TestNupService:
    @pytest.mark.parametrize(
        ("packages", "expected"),
        [
            pytest.param(
                [
                    Pkg(S2_BASE, KIND_BASE, 0),
                    Pkg(S2_BASE, KIND_UPDATE, 0x70000),
                    Pkg(0x040074A01BF13001, KIND_ADDON, 0),
                ],
                SigilExtractionResult(
                    "040074A01BF12000",
                    "040074A01BF12000",
                    "folder-exact",
                    "application",
                    0x70000,
                ),
                id="base",
            ),
            pytest.param(
                [Pkg(S1_BASE, KIND_UPDATE, 0x20000, FLAG_STANDALONE_UPDATE)],
                SigilExtractionResult(
                    "0100ABCD12340000",
                    "0100ABCD12340000",
                    "folder-exact",
                    "patch",
                    0x20000,
                ),
                id="update-only",
            ),
            pytest.param(
                [Pkg(0x0100ABCD12341003, KIND_ADDON, 0x10000)],
                SigilExtractionResult(
                    "0100ABCD12341003",
                    "0100ABCD12340000",
                    "folder-exact",
                    "addon",
                    0x10000,
                ),
                id="dlc-only",
            ),
            pytest.param(
                [Pkg(0x0100ABCD12341003, KIND_ADDON_UPDATE, 0x20000)],
                SigilExtractionResult(
                    "0100ABCD12341003",
                    "0100ABCD12340000",
                    "folder-exact",
                    "addon",
                    0x20000,
                ),
                id="dlc-update-only",
            ),
            pytest.param(
                [Pkg(0x0100000000000809, KIND_SYSTEM, 5)],
                SigilExtractionResult(
                    "0100000000000809",
                    "0100000000000000",
                    "folder-exact",
                    None,
                    5,
                ),
                id="system-only",
            ),
        ],
    )
    async def test_maps_the_primary_package(
        self,
        service: NupService,
        tmp_path: Path,
        packages: list[Pkg],
        expected: SigilExtractionResult,
    ):
        path = write(tmp_path, build_nup(packages))

        assert await service.extract_title_id(UPS.SWITCH_2, path) == expected

    async def test_warns_about_a_switch_2_file_in_switch(
        self, service: NupService, tmp_path: Path, mocker
    ):
        log = mocker.patch.object(nup_adapter, "log")
        path = write(tmp_path, build_nup([Pkg(S2_BASE)]))

        result = await service.extract_title_id(UPS.SWITCH, path)

        assert result is not None and result.title_id == "040074A01BF12000"
        log.warning.assert_called_once()
        assert "040074A01BF12000" in log.warning.call_args.args[0]

    @pytest.mark.parametrize(
        ("platform_slug", "title_id"),
        [
            pytest.param(UPS.SWITCH_2, S2_BASE, id="switch-2-in-switch-2"),
            pytest.param(UPS.SWITCH, S1_BASE, id="switch-1-in-switch"),
            pytest.param(UPS.SWITCH_2, S1_BASE, id="edition-in-switch-2"),
        ],
    )
    async def test_no_warning_otherwise(
        self,
        service: NupService,
        tmp_path: Path,
        mocker,
        platform_slug: str,
        title_id: int,
    ):
        log = mocker.patch.object(nup_adapter, "log")
        path = write(tmp_path, build_nup([Pkg(title_id)]))

        assert await service.extract_title_id(platform_slug, path) is not None
        log.warning.assert_not_called()

    @pytest.mark.parametrize(
        "data",
        [
            pytest.param(b"", id="empty"),
            pytest.param(build_nup([Pkg(S2_BASE)], corrupt="toc_hash"), id="corrupt"),
            pytest.param(b"PFS0" + b"\0" * 200, id="not-a-nup"),
        ],
    )
    async def test_invalid_file_logs_at_debug(
        self, service: NupService, tmp_path: Path, mocker, data: bytes
    ):
        log = mocker.patch.object(nup_adapter, "log")

        result = await service.extract_title_id(UPS.SWITCH, write(tmp_path, data))

        assert result is None
        log.debug.assert_called_once()
        log.warning.assert_not_called()
        log.error.assert_not_called()

    async def test_missing_file_logs_at_debug(
        self, service: NupService, tmp_path: Path, mocker
    ):
        log = mocker.patch.object(nup_adapter, "log")

        result = await service.extract_title_id(UPS.SWITCH, str(tmp_path / "gone.nup"))

        assert result is None
        log.debug.assert_called_once()
