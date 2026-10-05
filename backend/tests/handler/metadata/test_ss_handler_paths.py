"""ScreenScraper handler paths the main suite leaves out: every media type, the
filename formats a name search goes through, and each disabled or exhausted
short-circuit."""

import json
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status

from adapters.services.screenscraper import (
    ScreenScraperCredentialsError,
    SSCredentialSet,
)
from adapters.services.screenscraper_types import SSGame, SSGameMedia
from config.config_manager import Config, MetadataMediaType
from handler.metadata import ss_handler
from handler.metadata.ss_handler import (
    ARCADE_SS_ID,
    PS2_SS_ID,
    PSP_SS_ID,
    SWITCH_SS_ID,
    ScreenScraperExhaustedError,
    SSHandler,
    build_ss_game,
    extract_media_from_ss_game,
    extract_metadata_from_ss_rom,
    find_ss_dump,
)
from models.platform import Platform
from models.rom import LookupHashes, Rom, RomFile
from utils.platform_slugs import UniversalPlatformSlug as UPS


def _config(scan_media: list[str], languages: list[str] | None = None) -> Config:
    return Config(
        SCAN_REGION_MODE="prefer_rom_tags",
        EXCLUDED_PLATFORMS=[],
        EXCLUDED_SINGLE_EXT=[],
        EXCLUDED_SINGLE_FILES=[],
        EXCLUDED_MULTI_FILES=[],
        EXCLUDED_MULTI_PARTS_EXT=[],
        EXCLUDED_MULTI_PARTS_FILES=[],
        PLATFORMS_BINDING={},
        PLATFORMS_VERSIONS={},
        STRUCTURE_TEMPLATES={
            "default": "{platform}/roms/{game}",
            "firmware": "{platform}/bios",
        },
        SCAN_REGION_PRIORITY=["us"],
        SCAN_LANGUAGE_PRIORITY=languages or ["en"],
        SCAN_MEDIA=scan_media,
        GAMELIST_MEDIA_THUMBNAIL=MetadataMediaType.BOX2D,
    )


@pytest.fixture
def config() -> Iterator[Config]:
    """Every media type wanted, and media paths that name their type."""
    cfg = _config([m.value for m in MetadataMediaType])
    with (
        patch("handler.metadata.ss_handler.cm.get_config", return_value=cfg),
        patch(
            "handler.metadata.ss_handler.fs_resource_handler.get_media_resources_path",
            side_effect=lambda pid, rid, mt: f"roms/{pid}/{rid}/{mt.value}",
        ),
    ):
        yield cfg


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> SSHandler:
    monkeypatch.setattr(ss_handler, "SCREENSCRAPER_USER", "user")
    monkeypatch.setattr(ss_handler, "SCREENSCRAPER_PASSWORD", "password")
    return SSHandler()


def _rom() -> Rom:
    return Rom(
        id=7,
        platform_id=3,
        platform=Platform(slug="snes", fs_slug="snes", name="SNES"),
        regions=["USA"],
    )


def _media(kind: str, region: str = "us", support: str | None = None) -> SSGameMedia:
    media = SSGameMedia(
        type=kind,
        parent="jeu",
        url=f"https://ss.test/{kind}.png?ssid=user&sspassword=secret",
        region=region,
        crc="",
        md5="",
        sha1="",
        format="png",
    )
    if support is not None:
        media["support"] = support
    return media


def _game(*medias: SSGameMedia, game_id: str = "1", name: str = "Zelda") -> SSGame:
    return SSGame(
        id=game_id,
        noms=[{"region": "us", "text": name}],
        systeme={"id": "4", "text": "SNES"},
        topstaff=None,
        rotation="0",
        medias=list(medias),
    )


def _url(kind: str) -> str:
    return f"https://ss.test/{kind}.png"


class TestEveryMediaType:
    def test_each_type_lands_in_its_field_and_folder(self, config: Config):
        kinds = [
            "box-2D-back",
            "bezel-16-9",
            "box-2D",
            "fanart",
            "box-texture",
            "wheel-hd",
            "wheel",
            "manuel",
            "screenmarquee",
            "miximage1",
            "mixrbv2",
            "support-2D",
            "ss",
            "box-2D-side",
            "steamgrid",
            "box-3D",
            "sstitle",
            "video",
            "video-normalized",
        ]

        media = extract_media_from_ss_game(
            _rom(),
            _game(*(_media(k) for k in kinds), _media("support-2D", support="2")),
        )

        assert {k: v for k, v in media.items() if k.endswith("_url")} == {
            "bezel_url": _url("bezel-16-9"),
            "box2d_url": _url("box-2D"),
            "box2d_back_url": _url("box-2D-back"),
            "box2d_side_url": _url("box-2D-side"),
            "box3d_url": _url("box-3D"),
            "fanart_url": _url("fanart"),
            "fullbox_url": _url("box-texture"),
            "logo_url": _url("wheel-hd"),
            "manual_url": _url("manuel"),
            "marquee_url": _url("screenmarquee"),
            "miximage_url": _url("miximage1"),
            "miximage_v2_url": _url("mixrbv2"),
            "physical_url": _url("support-2D"),
            "screenshot_url": _url("ss"),
            "steamgrid_url": _url("steamgrid"),
            "title_screen_url": _url("sstitle"),
            "video_url": _url("video"),
            "video_normalized_url": _url("video-normalized"),
        }
        assert {k: v for k, v in media.items() if k.endswith("_path")} == {
            "bezel_path": "roms/3/7/bezel/bezel.png",
            "box2d_path": "roms/3/7/box2d/box2d.png",
            "box2d_back_path": "roms/3/7/box2d_back/box2d_back.png",
            "box2d_side_path": "roms/3/7/box2d_side/box2d_side.png",
            "box3d_path": "roms/3/7/box3d/box3d.png",
            "fanart_path": "roms/3/7/fanart/fanart.png",
            "miximage_path": "roms/3/7/miximage/miximage.png",
            "miximage_v2_path": "roms/3/7/miximage_v2/miximage_v2.png",
            "physical_path": "roms/3/7/physical/physical.png",
            "marquee_path": "roms/3/7/marquee/marquee.png",
            "logo_path": "roms/3/7/logo/logo.png",
            "title_screen_path": "roms/3/7/title_screen/title_screen.png",
            "video_path": "roms/3/7/video/video.mp4",
            "video_normalized_path": ("roms/3/7/video_normalized/video-normalized.mp4"),
        }
        assert media["physical_extra_discs"] == [
            {
                "disc": 2,
                "url": _url("support-2D"),
                "path": "roms/3/7/physical/physical_disc2.png",
            }
        ]

    def test_a_plain_wheel_is_the_logo_without_an_hd_one(self, config: Config):
        media = extract_media_from_ss_game(_rom(), _game(_media("wheel")))

        assert (media["logo_url"], media["logo_path"]) == (
            _url("wheel"),
            "roms/3/7/logo/logo.png",
        )

    def test_media_of_another_parent_are_ignored(self, config: Config):
        sibling = _media("box-2D")
        sibling["parent"] = "famille"

        assert extract_media_from_ss_game(_rom(), _game(sibling))["box2d_url"] is None


class TestMetadataEdges:
    def test_a_null_player_count_reads_as_one(self, config: Config):
        game = _game()
        game["joueurs"] = {"text": "null"}

        meta = extract_metadata_from_ss_rom(_rom(), game)

        assert meta["player_count"] == "1"

    def test_a_missing_preferred_language_falls_back_with_a_warning(
        self, config: Config
    ):
        game = _game()
        game["synopsis"] = [{"langue": "en", "text": "A quest."}]
        with (
            patch(
                "handler.metadata.ss_handler.cm.get_config",
                return_value=_config(["box2d"], languages=["fr", "en"]),
            ),
            patch.object(ss_handler, "log") as log,
        ):
            rom = build_ss_game(_rom(), game)

        assert rom.get("summary") == "A quest."
        log.warning.assert_called_once()

    def test_a_real_player_count_is_kept(self, config: Config):
        game = _game()
        game["joueurs"] = {"text": "1-4"}

        assert extract_metadata_from_ss_rom(_rom(), game)["player_count"] == "1-4"

    def test_a_date_from_an_unlisted_region_is_the_fallback(self, config: Config):
        game = _game()
        game["dates"] = [
            {"region": "br", "text": "not a date"},
            {"region": "br", "text": "1998-11-21"},
        ]

        meta = extract_metadata_from_ss_rom(_rom(), game)

        assert meta["first_release_date"] == 911606400

    def test_no_readable_date_has_none(self, config: Config):
        game = _game()
        game["dates"] = [{"region": "br", "text": "soon"}]

        assert extract_metadata_from_ss_rom(_rom(), game)["first_release_date"] is None

    def test_a_dump_entry_that_is_not_an_object_is_skipped(self):
        # Parsed the way a reply is, so a malformed entry can reach the handler.
        game: SSGame = json.loads(
            json.dumps({**_game(), "roms": ["junk", {"romcrc": "ABC"}]})
        )

        dump = find_ss_dump(game, LookupHashes(crc="abc", md5=None, sha1=None))

        assert dump == {"romcrc": "ABC"}

    def test_no_hashes_find_no_dump(self):
        assert (
            find_ss_dump(_game(), LookupHashes(crc=None, md5=None, sha1=None)) is None
        )


def _file(name: str = "Zelda.sfc") -> RomFile:
    return RomFile(
        file_name=name,
        file_path="snes/roms",
        file_size_bytes=1024,
        crc_hash="abc",
        md5_hash="",
        sha1_hash="",
    )


class TestShortCircuits:
    async def test_disabled_answers_nothing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(ss_handler, "SCREENSCRAPER_USER", "")
        handler = SSHandler()
        with patch.object(handler.ss_service, "get_game_info") as info:
            assert await handler.heartbeat() is False
            assert await handler.lookup_rom(_rom(), 4, [_file()]) == (
                {"ss_id": None},
                False,
            )
            assert await handler.get_rom(_rom(), "Zelda.sfc", 4) == {"ss_id": None}
            assert await handler.get_rom_by_id(_rom(), 1) == {"ss_id": None}
            assert await handler.get_matched_rom_by_id(_rom(), 1) is None
            assert await handler.get_matched_roms_by_name(_rom(), "Zelda", 4) == []
        info.assert_not_called()

    async def test_no_platform_answers_nothing(self, enabled: SSHandler):
        with patch.object(enabled.ss_service, "search_games") as search:
            assert await enabled.lookup_rom(_rom(), 0, [_file()]) == (
                {"ss_id": None},
                False,
            )
            assert await enabled.get_rom(_rom(), "Zelda.sfc", 0) == {"ss_id": None}
            assert await enabled._search_rom("Zelda", 0) is None
            assert await enabled.get_matched_roms_by_name(_rom(), "Zelda", None) == []
        search.assert_not_called()

    async def test_no_lookup_file_answers_nothing(self, enabled: SSHandler):
        empty = _file()
        empty.file_size_bytes = 0

        assert await enabled.lookup_rom(_rom(), 4, [empty]) == ({"ss_id": None}, False)


class TestHeartbeat:
    @pytest.mark.parametrize(
        ("reply", "healthy"),
        [
            ({"response": {"serveurs": {}}}, True),
            ({}, False),
            (None, False),
            (HTTPException(status_code=503), False),
        ],
        ids=["answers", "empty", "none", "down"],
    )
    async def test_reports_whether_screenscraper_answers(
        self, enabled: SSHandler, reply: object, healthy: bool
    ):
        effect = reply if isinstance(reply, Exception) else None
        with patch.object(
            enabled.ss_service,
            "get_infra_info",
            AsyncMock(return_value=reply, side_effect=effect),
        ):
            assert await enabled.heartbeat() is healthy


def _named(game_id: str, *names: str, notgame: bool = False) -> SSGame:
    game = _game(game_id=game_id, name=names[0])
    game["noms"] = [{"region": "us", "text": n} for n in names]
    if notgame:
        game["notgame"] = "true"
    return game


class TestSearch:
    async def test_skips_notgames_and_keeps_the_oldest_of_a_shared_name(
        self, enabled: SSHandler
    ):
        results = [
            _named("30", "Zelda"),
            _named("10", "Zelda"),
            _named("5", "Zelda", notgame=True),
            _named("20", "Zelda"),
        ]
        with patch.object(
            enabled.ss_service, "search_games", AsyncMock(return_value=results)
        ):
            game = await enabled._search_rom("Zelda", 4)

        assert game is not None and game["id"] == "10"

    async def test_no_close_name_is_no_match(self, enabled: SSHandler):
        with patch.object(
            enabled.ss_service,
            "search_games",
            AsyncMock(return_value=[_named("1", "Metroid")]),
        ):
            assert await enabled._search_rom("Zelda", 4) is None

    async def test_matched_roms_keep_ss_region_games_only(
        self, enabled: SSHandler, config: Config
    ):
        ss_named = _named("1", "Zelda")
        ss_named["noms"] = [{"region": "ss", "text": "Zelda"}]
        results = [ss_named, _named("2", "Zelda"), _named("3", "Zelda", notgame=True)]
        with patch.object(
            enabled.ss_service, "search_games", AsyncMock(return_value=results)
        ):
            roms = await enabled.get_matched_roms_by_name(_rom(), "Zelda", 4)

        assert [r.get("ss_id") for r in roms] == [1]


def _exhausted() -> HTTPException:
    return ScreenScraperCredentialsError(SSCredentialSet.USER)


class TestExhausted:
    async def test_a_manual_match_by_id_moves_on(self, enabled: SSHandler):
        with patch.object(
            enabled.ss_service, "get_game_info", AsyncMock(side_effect=_exhausted())
        ):
            assert await enabled.get_matched_rom_by_id(_rom(), 1) is None

    async def test_a_name_list_has_no_matches(self, enabled: SSHandler):
        with patch.object(
            enabled.ss_service, "search_games", AsyncMock(side_effect=_exhausted())
        ):
            assert await enabled.get_matched_roms_by_name(_rom(), "Zelda", 4) == []

    async def test_another_error_still_fails_the_name_list(self, enabled: SSHandler):
        down = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        with (
            patch.object(
                enabled.ss_service, "search_games", AsyncMock(side_effect=down)
            ),
            pytest.raises(HTTPException),
        ):
            await enabled.get_matched_roms_by_name(_rom(), "Zelda", 4)

    async def test_a_search_carries_the_name_it_derived(self, enabled: SSHandler):
        with (
            patch.object(enabled, "_mame_format", AsyncMock(return_value="Pac-Man")),
            patch.object(
                enabled.ss_service, "search_games", AsyncMock(side_effect=_exhausted())
            ),
            pytest.raises(ScreenScraperExhaustedError) as exc,
        ):
            await enabled.get_rom(_rom(), "pacman.zip", ARCADE_SS_ID)

        assert exc.value.fallback == {"ss_id": None, "name": "Pac-Man"}


class TestById:
    async def test_a_manual_match_returns_the_game(
        self, enabled: SSHandler, config: Config
    ):
        with patch.object(
            enabled.ss_service,
            "get_game_info",
            AsyncMock(return_value=_game(game_id="42")),
        ):
            rom = await enabled.get_matched_rom_by_id(_rom(), 42)

        assert rom is not None and rom.get("ss_id") == 42

    async def test_no_lookup_file_attaches_no_dump_tags(
        self, enabled: SSHandler, config: Config
    ):
        with patch.object(
            enabled.ss_service,
            "get_game_info",
            AsyncMock(return_value=_game(game_id="42")),
        ):
            rom = await enabled.get_rom_by_id(_rom(), 42, files=[])

        assert rom.get("ss_id") == 42
        assert "tags" not in rom


class TestGetRom:
    @pytest.fixture
    def search(self, enabled: SSHandler) -> Iterator[AsyncMock]:
        with patch.object(
            enabled.ss_service, "search_games", AsyncMock(return_value=[])
        ) as search:
            yield search

    async def test_a_tag_fetches_the_game_by_id(
        self, enabled: SSHandler, config: Config
    ):
        with patch.object(
            enabled.ss_service,
            "get_game_info",
            AsyncMock(return_value=_game(game_id="42")),
        ) as info:
            rom = await enabled.get_rom(_rom(), "Zelda (ssfr-42).sfc", 4)

        assert rom.get("ss_id") == 42
        info.assert_awaited_once_with(game_id=42)

    async def test_a_tag_not_found_falls_back_to_the_name(
        self, enabled: SSHandler, config: Config, search: AsyncMock
    ):
        with patch.object(
            enabled.ss_service, "get_game_info", AsyncMock(return_value=None)
        ):
            rom = await enabled.get_rom(_rom(), "Zelda (ssfr-42).sfc", 4)

        assert rom == {"ss_id": None}
        assert search.await_args is not None
        assert search.await_args.kwargs["term"] == "zelda"

    async def test_a_name_that_is_only_tags_searches_nothing(
        self, enabled: SSHandler, search: AsyncMock
    ):
        assert await enabled.get_rom(_rom(), "(USA).sfc", 4) == {"ss_id": None}
        search.assert_not_awaited()

    async def test_a_subtitle_retries_with_its_last_part(
        self, enabled: SSHandler, config: Config, search: AsyncMock
    ):
        search.side_effect = [[], [_named("9", "Ocarina of Time")]]

        rom = await enabled.get_rom(
            _rom(), "The Legend of Zelda : Ocarina of Time.z64", 4
        )

        assert rom.get("ss_id") == 9
        assert search.await_args is not None
        assert search.await_args.kwargs["term"] == " Ocarina of Time"

    @pytest.mark.parametrize(
        ("file_name", "platform_ss_id", "helper"),
        [
            ("SLUS_200.62.Grand Theft Auto.iso", PS2_SS_ID, "_ps2_opl_format"),
            ("Ridge Racer [SLUS-01234].iso", PS2_SS_ID, "_ps2_serial_format"),
            ("Lumines [ULUS-10046].iso", PSP_SS_ID, "_psp_serial_format"),
            ("pacman.zip", ARCADE_SS_ID, "_mame_format"),
        ],
        ids=["ps2_opl", "ps2_serial", "psp_serial", "arcade"],
    )
    async def test_a_platform_format_names_the_search_and_the_fallback(
        self,
        enabled: SSHandler,
        search: AsyncMock,
        file_name: str,
        platform_ss_id: int,
        helper: str,
    ):
        with patch.object(enabled, helper, AsyncMock(return_value="Resolved")):
            rom = await enabled.get_rom(_rom(), file_name, platform_ss_id)

        assert rom == {"ss_id": None, "name": "Resolved"}
        assert search.await_args is not None
        assert search.await_args.kwargs["term"] == "resolved"

    async def test_a_scummvm_name_is_resolved(
        self, enabled: SSHandler, search: AsyncMock
    ):
        scummvm = enabled.get_platform(UPS.SCUMMVM).get("ss_id")
        assert isinstance(scummvm, int)
        with patch.object(
            enabled, "_scummvm_format", AsyncMock(return_value="Monkey Island")
        ):
            rom = await enabled.get_rom(_rom(), "monkey1.scummvm", scummvm)

        assert rom == {"ss_id": None, "name": "Monkey Island"}

    async def test_a_switch_product_id_names_the_fallback(
        self, enabled: SSHandler, search: AsyncMock
    ):
        entry = {
            "name": "Celeste",
            "description": "Climb.",
            "iconUrl": "https://titledb.test/celeste.png",
            "screenshots": None,
        }
        with patch.object(
            enabled,
            "_switch_productid_format",
            AsyncMock(return_value=("Celeste", entry)),
        ):
            rom = await enabled.get_rom(_rom(), "Celeste.nsp", SWITCH_SS_ID)

        assert rom == {
            "ss_id": None,
            "name": "Celeste",
            "summary": "Climb.",
            "url_cover": "https://titledb.test/celeste.png",
            "url_screenshots": [],
        }
