import types
from pathlib import Path
from unittest.mock import Mock

import pytest

import adapters.services.sigil as sigil_adapter
from adapters.services.sigil import SigilExtractionResult, SigilService
from models.platform import Platform
from models.rom import Rom, RomFile, RomFileCategory
from utils.platform_slugs import UniversalPlatformSlug as UPS


class FakeSigilError(Exception):
    def __init__(self, code: int):
        super().__init__(f"sigil error {code}")
        self.code = code


class FakeNotFoundError(FakeSigilError): ...


class FakeUnsupportedFormatError(FakeSigilError): ...


class FakeNeedsKeyError(FakeSigilError): ...


def make_fake_sigil(extract: Mock) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        extract=extract,
        SigilNotFoundError=FakeNotFoundError,
        SigilUnsupportedFormatError=FakeUnsupportedFormatError,
        SigilNeedsKeyError=FakeNeedsKeyError,
    )


def patch_log_error(monkeypatch) -> Mock:
    log_error = Mock()
    monkeypatch.setattr("adapters.services.sigil.log.error", log_error)
    return log_error


def make_result(
    title_id: str = "0100ABCD12340000",
    save_id: str = "0100ABCD12340000",
    usage: str = "folder-exact",
    switch_content_type: str | None = None,
    title_version: int | None = None,
    raw_serial: str = "",
    features: int = 0,
    n64_header: str = "",
    n64_md5: str = "",
    n64_md5_n64: str = "",
) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        title_id=title_id,
        save_id=save_id,
        usage=usage,
        switch_content_type=switch_content_type,
        title_version=title_version,
        raw_serial=raw_serial,
        features=features,
        n64_header=n64_header,
        n64_md5=n64_md5,
        n64_md5_n64=n64_md5_n64,
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

        result = await service.extract_title_id(UPS.NES, "/roms/nes/game.nes")

        assert result is None
        extract.assert_not_called()

    @pytest.mark.asyncio
    async def test_maps_the_n64_identity(self, service: SigilService, monkeypatch):
        extract = Mock(
            return_value=make_result(
                title_id="NTEA",
                save_id="NTEA",
                n64_header="1080 SNOWBOARDING",
                n64_md5="FA27089C425DBAB99F19245C5C997613",
                n64_md5_n64="10C93DD78B695CD32B6938534ED0EDD5",
            )
        )
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.N64, "/roms/n64/1080.z64")

        assert result is not None
        assert (result.n64_header, result.n64_md5, result.n64_md5_n64) == (
            "1080 SNOWBOARDING",
            "FA27089C425DBAB99F19245C5C997613",
            "10C93DD78B695CD32B6938534ED0EDD5",
        )
        extract.assert_called_once_with(
            "/roms/n64/1080.z64", platform="n64", filename_fallback=False
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("slug", "sigil_slug"), [(UPS.GB, "gb"), (UPS.GBC, "gbc")])
    async def test_reads_a_game_boy_carts_features(
        self, service: SigilService, monkeypatch, slug: str, sigil_slug: str
    ):
        extract = Mock(return_value=make_result(title_id="", save_id="", features=1))
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(slug, "/roms/gb/game.gb")

        assert result is not None
        assert (result.title_id, result.features) == ("", 1)
        assert extract.call_args.kwargs["platform"] == sigil_slug

    @pytest.mark.asyncio
    async def test_successful_extraction_maps_fields(
        self, service: SigilService, monkeypatch
    ):
        extract = Mock(
            return_value=make_result(
                title_id="SLUS-20152",
                save_id="BASLUS-20152",
                usage="folder-prefix",
                raw_serial="SLUS_201.52",
                features=1,
            )
        )
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.PS2, "/roms/ps2/game.iso")

        assert result == SigilExtractionResult(
            title_id="SLUS-20152",
            save_target="BASLUS-20152",
            usage="folder-prefix",
            raw_serial="SLUS_201.52",
            features=1,
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
    @pytest.mark.parametrize(
        "error",
        [FakeNotFoundError(-5), FakeUnsupportedFormatError(-4), FakeNeedsKeyError(-6)],
    )
    async def test_routine_sigil_error_returns_none_quietly(
        self, service: SigilService, monkeypatch, error: FakeSigilError
    ):
        extract = Mock(side_effect=error)
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))
        log_error = patch_log_error(monkeypatch)

        result = await service.extract_title_id(UPS.PSX, "/roms/psx/game.bin")

        assert result is None
        log_error.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "error", [OSError("native crash"), FakeSigilError(-2)], ids=["os", "io"]
    )
    async def test_unexpected_error_returns_none_and_is_logged(
        self, service: SigilService, monkeypatch, error: Exception
    ):
        extract = Mock(side_effect=error)
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))
        log_error = patch_log_error(monkeypatch)

        result = await service.extract_title_id(UPS.PS2, "/roms/ps2/game.iso")

        assert result is None
        log_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_playlist_is_its_first_disc_and_lists_every_discs_id(
        self, service: SigilService, monkeypatch, tmp_path: Path
    ):
        ids = {
            "Game (Disc 1).chd": "SLUS-21359",
            "Game (Disc 2).chd": "SLUS-21360",
            "Game (Disc 3).chd": "",
        }
        for name in ids:
            (tmp_path / name).write_bytes(b"disc")
        playlist = tmp_path / "Game.m3u"
        playlist.write_text(
            "Game (Disc 1).chd\nGame (Disc 2).chd\nGame (Disc 3).chd\nMissing.chd\n"
        )
        extract = Mock(
            side_effect=lambda path, **_: make_result(title_id=ids[Path(path).name])
        )
        monkeypatch.setattr(sigil_adapter, "sigil", make_fake_sigil(extract))

        result = await service.extract_title_id(UPS.PS2, str(playlist))

        assert result is not None
        assert result.title_id == "SLUS-21359"
        assert result.playlist_title_ids == ("SLUS-21359", "SLUS-21360")
        assert [c.args[0] for c in extract.call_args_list] == [
            str(tmp_path / name) for name in ids
        ]

    @pytest.mark.asyncio
    async def test_a_single_file_has_no_playlist_ids(
        self, service: SigilService, monkeypatch
    ):
        monkeypatch.setattr(
            sigil_adapter, "sigil", make_fake_sigil(Mock(return_value=make_result()))
        )

        result = await service.extract_title_id(UPS.PS2, "/roms/ps2/game.iso")

        assert result is not None
        assert result.playlist_title_ids is None

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


def make_rom(
    slug: str = UPS.PSX, title_id: str | None = "SLUS-00892", save_target="SLUS-00892"
) -> Rom:
    return Rom(
        id=1,
        fs_name="Final Fantasy VIII",
        fs_path="psx/roms",
        title_id=title_id,
        save_target=save_target,
        platform=Platform(name="Platform", slug=slug, fs_slug=slug),
    )


def make_disc(
    name: str,
    title_id: str | None,
    raw_serial: str | None = None,
    features: int | None = None,
    category: RomFileCategory | None = None,
    **identity: object,
) -> RomFile:
    return RomFile(
        file_name=name,
        file_path="psx/roms/Final Fantasy VIII",
        title_id=title_id,
        raw_serial=raw_serial,
        sigil_features=features,
        category=category,
        **identity,
    )


NO_N64 = {"n64_header": "", "n64_md5": "", "n64_md5_n64": ""}


def persisted_kwargs(**kwargs: object) -> dict[str, object]:
    return kwargs


@pytest.fixture
def fake_sigil(monkeypatch) -> types.SimpleNamespace:
    fake = types.SimpleNamespace(
        SigilResult=types.SimpleNamespace(persisted=persisted_kwargs)
    )
    monkeypatch.setattr(sigil_adapter, "sigil", fake)
    return fake


class TestStoredGame:
    def test_rebuilds_disc_ones_result_with_every_disc_id(self, fake_sigil):
        files = [
            make_disc("FF8 (Disc 3).chd", "SLUS-00909"),
            make_disc("FF8 (Disc 10).chd", "SLUS-00910"),
            make_disc("FF8 (Disc 2).chd", "SLUS-00908", "SLUS_009.08", 0),
            make_disc("FF8 (Disc 1).chd", "SLUS-00892", "SLUS_008.92", 1),
            make_disc("FF8.m3u", "SLUS-00892", "SLUS_008.92", 1),
            make_disc("Bonus.chd", "SLUS-99999", category=RomFileCategory.DLC),
        ]

        game = SigilService.stored_game(make_rom(), files)

        assert game is not None
        assert game.result == {
            "platform": "psx",
            "title_id": "SLUS-00892",
            "save_id": "SLUS-00892",
            "features": 1,
            "raw_serial": "SLUS_008.92",
            **NO_N64,
        }
        assert game.game_ids == (
            "SLUS-00892",
            "SLUS-00908",
            "SLUS-00909",
            "SLUS-00910",
        )

    def test_unread_files_rebuild_as_a_fresh_extraction_would(self, fake_sigil):
        files = [make_disc("FF8 (Disc 1).chd", "SLUS-00892")]

        game = SigilService.stored_game(make_rom(save_target=None), files)

        assert game is not None
        assert game.result == {
            "platform": "psx",
            "title_id": "SLUS-00892",
            "save_id": "",
            "features": 0,
            "raw_serial": "",
            **NO_N64,
        }
        assert game.game_ids == ("SLUS-00892",)

    def test_the_rom_id_leads_when_no_file_carries_it(self, fake_sigil):
        files = [make_disc("Game.nsp", "0100ABCD12340800", "", 0)]

        game = SigilService.stored_game(
            make_rom(UPS.SWITCH, "0100ABCD12340000", "0100ABCD12340000"), files
        )

        assert game is not None
        assert game.result["features"] == 0
        assert game.game_ids == ("0100ABCD12340000", "0100ABCD12340800")

    def test_every_disc_a_playlist_lists_is_a_game_id(self, fake_sigil):
        files = [
            make_disc(
                "FF8.m3u",
                "SLUS-00892",
                features=0,
                playlist_title_ids=["SLUS-00892", "SLUS-00908", "SLUS-00909"],
            )
        ]

        game = SigilService.stored_game(make_rom(), files)

        assert game is not None
        assert game.game_ids == ("SLUS-00892", "SLUS-00908", "SLUS-00909")

    def test_carries_the_n64_identity(self, fake_sigil):
        n64 = {
            "n64_header": "1080 SNOWBOARDING",
            "n64_md5": "FA27089C425DBAB99F19245C5C997613",
            "n64_md5_n64": "10C93DD78B695CD32B6938534ED0EDD5",
        }
        files = [
            make_disc(
                "1080.z64",
                "NTEA",
                features=0,
                n64_header=n64["n64_header"],
                n64_md5=n64["n64_md5"],
                n64_md5_n64=n64["n64_md5_n64"],
            )
        ]

        game = SigilService.stored_game(make_rom(UPS.N64, "NTEA", "NTEA"), files)

        assert game is not None
        assert game.result == {
            "platform": "n64",
            "title_id": "NTEA",
            "save_id": "NTEA",
            "features": 0,
            "raw_serial": "",
            **n64,
        }

    @pytest.mark.parametrize(
        ("slug", "sigil_slug"),
        [(UPS.GBC, "gbc"), (UPS.SATURN, "saturn"), (UPS.SEGACD, "segacd")],
    )
    def test_a_platform_without_title_ids_still_restores(
        self, fake_sigil, slug: str, sigil_slug: str
    ):
        files = [make_disc("Game.gbc", None, features=1)]

        game = SigilService.stored_game(make_rom(slug, None, None), files)

        assert game is not None
        assert game.result["platform"] == sigil_slug
        assert (game.result["title_id"], game.result["features"]) == ("", 1)
        assert game.game_ids == ()

    @pytest.mark.parametrize(
        ("save_target", "title_id"),
        [("525a4445", "525A4445"), ("00010001/574b5445", "00010001574B5445")],
    )
    def test_a_wii_save_id_carries_its_category_only_for_a_wad(
        self, fake_sigil, save_target: str, title_id: str
    ):
        files = [make_disc("Game.wad", title_id, features=0)]

        game = SigilService.stored_game(make_rom(UPS.WII, title_id, save_target), files)

        assert game is not None
        assert game.result["platform"] == "wii"
        assert game.result["save_id"] == save_target
        assert game.game_ids == (title_id,)

    @pytest.mark.parametrize("slug", [UPS.NES, UPS.XBOX, UPS.XBOX360])
    def test_none_where_sigil_restores_no_saves(self, fake_sigil, slug: str):
        assert SigilService.stored_game(make_rom(slug), []) is None

    def test_none_when_binding_absent(self, monkeypatch):
        monkeypatch.setattr(sigil_adapter, "sigil", None)

        assert SigilService.stored_game(make_rom(), []) is None


class TestStoredGameAgainstTheBinding:
    """Runs where the binding is built (the Docker image, a local build)."""

    def test_rebuilds_a_real_sigil_result(self):
        binding = pytest.importorskip("sigil")
        files = [make_disc("FF8 (Disc 1).chd", "SLUS-00892", "SLUS_008.92", 1)]

        game = SigilService.stored_game(make_rom(), files)

        assert game is not None
        assert isinstance(game.result, binding.SigilResult)
        assert (game.result.raw_serial, game.result.has_rtc) == ("SLUS_008.92", True)

    @pytest.mark.asyncio
    async def test_a_file_without_a_title_id_is_routine(
        self, tmp_path: Path, monkeypatch
    ):
        pytest.importorskip("sigil")
        game = tmp_path / "game.iso"
        # Large enough to hold the volume descriptors, so the read succeeds.
        game.write_bytes(b"\0" * (1 << 20))
        log_error = patch_log_error(monkeypatch)

        result = await SigilService().extract_title_id(UPS.PS2, str(game))

        assert result is None
        log_error.assert_not_called()
