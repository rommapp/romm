"""
Tests for the LaunchBox metadata handler.

Covers:
  - utils.py          — pure utility functions
  - platforms.py      — platform slug resolution
  - local_source.py   — LocalSource (local XML parsing + Redis index cache)
  - remote_source.py  — RemoteSource (Redis metadata lookups)
  - handler.py        — LaunchboxHandler orchestration
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anyio import Path as AnyioPath
from defusedxml import ElementTree as ET

from handler.metadata.launchbox_handler.handler import LaunchboxHandler
from handler.metadata.launchbox_handler.local_source import LocalSource
from handler.metadata.launchbox_handler.media import (
    _get_video,
    build_launchbox_metadata,
    build_rom,
    populate_rom_specific_paths,
    remote_media_req,
)
from handler.metadata.launchbox_handler.platforms import get_platform
from handler.metadata.launchbox_handler.remote_source import RemoteSource
from handler.metadata.launchbox_handler.types import (
    LAUNCHBOX_MAME_KEY,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    LaunchboxImage,
    LaunchboxMetadata,
    MediaRequest,
)
from handler.metadata.launchbox_handler.utils import (
    coalesce,
    parse_playmode,
    parse_release_date,
    parse_videourl,
    sanitize_filename,
)
from handler.redis_handler import async_cache

# ---------------------------------------------------------------------------
# Sample XML that mirrors a real LaunchBox platform file
# ---------------------------------------------------------------------------

SAMPLE_NES_XML = """\
<?xml version="1.0"?>
<LaunchBox>
  <Game>
    <Title>Super Mario Bros.</Title>
    <ApplicationPath>Games\\NES\\super mario bros..nes</ApplicationPath>
    <DatabaseID>1234</DatabaseID>
    <Developer>Nintendo</Developer>
    <Publisher>Nintendo</Publisher>
    <Genre>Platformer</Genre>
    <ReleaseDate>1985-09-13T00:00:00</ReleaseDate>
    <MaxPlayers>2</MaxPlayers>
    <Region>North America</Region>
    <VideoUrl>https://www.youtube.com/watch?v=dQw4w9WgXcQ</VideoUrl>
    <CommunityStarRating>4.5</CommunityStarRating>
    <CommunityStarRatingTotalVotes>1000</CommunityStarRatingTotalVotes>
  </Game>
  <Game>
    <Title>Mega Man 2</Title>
    <ApplicationPath>Games\\NES\\Mega Man 2.nes</ApplicationPath>
    <DatabaseID>5678</DatabaseID>
    <Developer>Capcom</Developer>
    <Publisher>Capcom</Publisher>
    <Genre>Platformer;Action</Genre>
  </Game>
</LaunchBox>
"""

REMOTE_ENTRY = {
    "DatabaseID": "1234",
    "Name": "Super Mario Bros.",
    "Overview": "Jump and run platformer by Nintendo.",
    "MaxPlayers": "2",
    "ReleaseDate": "1985-09-13T00:00:00",
    "Developer": "Nintendo",
    "Publisher": "Nintendo",
    "Genres": "Platformer",
    "ESRB": "E - Everyone",
    "CommunityRating": "4.5",
    "CommunityRatingCount": "1000",
}

REMOTE_IMAGES = [
    {
        "FileName": "covers/super-mario-bros-front.png",
        "Type": "Box - Front",
        "Region": "North America",
    },
    {
        "FileName": "screens/super-mario-bros-1.png",
        "Type": "Screenshot - Gameplay",
        "Region": "",
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def platforms_dir(tmp_path: Path) -> Path:
    """Return a temporary Platforms directory (mirrors LaunchBox layout)."""
    d = tmp_path / "Data" / "Platforms"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def nes_xml(platforms_dir: Path) -> Path:
    """Write a sample NES XML to the temporary platforms dir."""
    xml_file = platforms_dir / "Nintendo Entertainment System.xml"
    xml_file.write_text(SAMPLE_NES_XML)
    return xml_file


# ===========================================================================
# TestUtils
# ===========================================================================


class TestSanitizeFilename:
    def test_basic_string(self):
        assert sanitize_filename("Super Mario Bros") == "Super Mario Bros"

    def test_strips_whitespace(self):
        assert sanitize_filename("  Game  ") == "Game"

    def test_replaces_curly_apostrophe(self):
        assert sanitize_filename("Mario\u2019s Game") == "Mario_s Game"

    def test_replaces_colon(self):
        assert sanitize_filename("Game: The Sequel") == "Game_ The Sequel"

    def test_replaces_backslash_and_pipe(self):
        assert sanitize_filename("A|B\\C") == "A_B_C"

    def test_collapses_multiple_spaces(self):
        assert sanitize_filename("A   B") == "A B"

    def test_collapses_multiple_underscores(self):
        assert sanitize_filename("A__B") == "A_B"

    def test_strips_trailing_dot(self):
        assert sanitize_filename("Game.") == "Game"

    def test_empty_string(self):
        assert sanitize_filename("") == ""


class TestCoalesce:
    def test_returns_first_non_empty(self):
        assert coalesce("hello", "world") == "hello"

    def test_skips_none(self):
        assert coalesce(None, "second") == "second"

    def test_skips_blank_string(self):
        assert coalesce("  ", "fallback") == "fallback"

    def test_all_none_returns_none(self):
        assert coalesce(None, None) is None

    def test_strips_result(self):
        assert coalesce("  hello  ") == "hello"


class TestParseReleaseDate:
    def test_iso_with_timezone_suffix(self):
        ts = parse_release_date("1985-09-13T00:00:00Z")
        assert isinstance(ts, int)
        assert ts > 0

    def test_iso_without_timezone(self):
        ts = parse_release_date("1985-09-13T00:00:00")
        assert isinstance(ts, int)

    def test_plain_date(self):
        ts = parse_release_date("1985-09-13")
        assert isinstance(ts, int)

    def test_none_input(self):
        assert parse_release_date(None) is None

    def test_empty_string(self):
        assert parse_release_date("") is None

    def test_invalid_format(self):
        assert parse_release_date("not-a-date") is None


class TestParsePlaymode:
    def test_cooperative(self):
        assert parse_playmode("Cooperative") is True

    def test_coop(self):
        assert parse_playmode("Coop") is True

    def test_co_op(self):
        assert parse_playmode("Co-op") is True

    def test_single_player(self):
        assert parse_playmode("Single Player") is False

    def test_none(self):
        assert parse_playmode(None) is False

    def test_empty(self):
        assert parse_playmode("") is False


class TestParseVideourl:
    def test_youtube_watch(self):
        assert (
            parse_videourl("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            == "dQw4w9WgXcQ"
        )

    def test_youtube_watch_with_extra_params(self):
        assert parse_videourl("https://www.youtube.com/watch?v=abc123&t=30") == "abc123"

    def test_youtu_be(self):
        assert parse_videourl("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_youtu_be_with_query(self):
        assert parse_videourl("https://youtu.be/abc123?t=30") == "abc123"

    def test_non_youtube(self):
        assert parse_videourl("https://vimeo.com/123456") == ""

    def test_none(self):
        assert parse_videourl(None) == ""

    def test_empty(self):
        assert parse_videourl("") == ""


# ===========================================================================
# TestPlatforms
# ===========================================================================


class TestGetPlatform:
    def test_known_slug(self):
        p = get_platform("nes")
        assert p.get("launchbox_id", None) == 27
        assert p.get("name", None) == "Nintendo Entertainment System"
        assert p.get("slug", None) == "nes"

    def test_case_insensitive(self):
        p = get_platform("NES")
        assert p.get("launchbox_id", None) == 27

    def test_unknown_slug_returns_none_id(self):
        p = get_platform("unknown-platform-xyz")
        assert p["launchbox_id"] is None
        assert p.get("slug", None) == "unknown-platform-xyz"

    def test_slug_with_dashes_normalized(self):
        # n64 is registered as UPS.N64 = "n64"
        p = get_platform("n64")
        assert p.get("launchbox_id", None) == 25

    def test_slug_strips_whitespace(self):
        p = get_platform("  nes  ")
        assert p.get("launchbox_id", None) == 27


# ===========================================================================
# TestLocalSource
# ===========================================================================


class TestLocalSource:
    @pytest.fixture
    def source(self) -> LocalSource:
        return LocalSource()

    async def test_platforms_dir_missing_returns_none(self, source: LocalSource):
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            Path("/nonexistent/path/that/does/not/exist"),
        ):
            result = await source.get_rom("game.nes", "nes")
        assert result is None

    async def test_unknown_platform_returns_none(
        self, source: LocalSource, platforms_dir: Path
    ):
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            # "unknown-xyz" has no XML file in platforms_dir
            result = await source.get_rom("game.nes", "unknown-xyz")
        assert result is None

    async def test_xml_file_missing_returns_none(
        self, source: LocalSource, platforms_dir: Path
    ):
        # platforms_dir exists but "Nintendo Entertainment System.xml" is not created
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            result = await source.get_rom("game.nes", "nes")
        assert result is None

    async def test_match_by_application_path(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            result = await source.get_rom("super mario bros..nes", "nes")

        assert result is not None
        assert result.get("Title", None) == "Super Mario Bros."
        assert result.get("DatabaseID", None) == "1234"

    async def test_match_by_title_stem(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        """Filename stem should match the Title key in the index."""
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            # "Mega Man 2.nes" → stem "Mega Man 2" → title key "mega man 2"
            result = await source.get_rom("Mega Man 2.nes", "nes")

        assert result is not None
        assert result.get("Title", None) == "Mega Man 2"

    async def test_cache_hit_uses_cached_index(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        cached_index = {
            "super mario bros..nes": {"Title": "Cached Entry", "DatabaseID": "9999"}
        }
        source._cache["nes"] = cached_index
        source._mtime["nes"] = nes_xml.stat().st_mtime_ns  # trunk-ignore(ruff/ASYNC240)

        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            with patch(
                "handler.metadata.launchbox_handler.local_source.ET.parse"
            ) as mock_parse:
                result = await source.get_rom("super mario bros..nes", "nes")
                mock_parse.assert_not_called()

        assert result is not None
        assert result.get("Title", None) == "Cached Entry"

    async def test_xml_parsed_once_across_calls(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        """XML should only be parsed once per platform per LocalSource lifetime."""
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            with patch(
                "handler.metadata.launchbox_handler.local_source.ET.parse",
                wraps=ET.parse,
            ) as mock_parse:
                await source.get_rom("super mario bros..nes", "nes")
                await source.get_rom("Mega Man 2.nes", "nes")
                mock_parse.assert_called_once()

    async def test_parse_error_returns_none(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        await AnyioPath(str(nes_xml)).write_text("<<<not valid xml>>>")

        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            result = await source.get_rom("super mario bros..nes", "nes")

        assert result is None

    async def test_empty_fs_name_returns_none(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            result = await source.get_rom("   ", "nes")

        assert result is None

    async def test_no_match_returns_none(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            result = await source.get_rom("game_that_does_not_exist.nes", "nes")

        assert result is None


# ===========================================================================
# TestRemoteSource
# ===========================================================================


class TestRemoteSourceGetById:
    @pytest.fixture
    def source(self) -> RemoteSource:
        return RemoteSource()

    async def test_cache_miss_returns_none(self, source: RemoteSource):
        with patch.object(
            async_cache, "hget", new_callable=AsyncMock, return_value=None
        ):
            result = await source.get_by_id(1234)
        assert result is None

    async def test_cache_hit_returns_dict(self, source: RemoteSource):
        with patch.object(
            async_cache,
            "hget",
            new_callable=AsyncMock,
            return_value=json.dumps(REMOTE_ENTRY),
        ):
            result = await source.get_by_id(1234)
        assert result is not None
        assert result.get("Name", None) == "Super Mario Bros."

    async def test_accepts_string_id(self, source: RemoteSource):
        with patch.object(
            async_cache,
            "hget",
            new_callable=AsyncMock,
            return_value=json.dumps(REMOTE_ENTRY),
        ) as mock_hget:
            await source.get_by_id("1234")
        mock_hget.assert_called_once_with(LAUNCHBOX_METADATA_DATABASE_ID_KEY, "1234")


class TestRemoteSourceGetRom:
    @pytest.fixture
    def source(self) -> RemoteSource:
        return RemoteSource()

    async def test_no_cache_returns_none(self, source: RemoteSource):
        with patch.object(
            async_cache, "exists", new_callable=AsyncMock, return_value=False
        ):
            result = await source.get_rom("super mario bros.", "nes")
        assert result is None

    async def test_unknown_platform_returns_none(self, source: RemoteSource):
        with patch.object(
            async_cache, "hget", new_callable=AsyncMock, return_value=None
        ):
            result = await source.get_rom(
                "game", "unknown-xyz", assume_cache_present=True
            )
        assert result is None

    async def test_name_match_returns_entry(self, source: RemoteSource):
        with patch.object(
            async_cache,
            "hget",
            new_callable=AsyncMock,
            return_value=json.dumps(REMOTE_ENTRY),
        ):
            result = await source.get_rom(
                "super mario bros.", "nes", assume_cache_present=True
            )
        assert result is not None
        assert result.get("DatabaseID", None) == "1234"

    async def test_alternate_name_match(self, source: RemoteSource):
        alt_entry = {"DatabaseID": "1234"}

        async def side_effect(key, _field):
            if key == LAUNCHBOX_METADATA_NAME_KEY:
                return None
            if key == LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY:
                return json.dumps(alt_entry)
            if key == LAUNCHBOX_METADATA_DATABASE_ID_KEY:
                return json.dumps(REMOTE_ENTRY)
            return None

        with patch.object(
            async_cache, "hget", new_callable=AsyncMock, side_effect=side_effect
        ):
            result = await source.get_rom(
                "super mario bros.", "nes", assume_cache_present=True
            )
        assert result is not None
        assert result.get("Name", None) == "Super Mario Bros."

    async def test_no_match_returns_none(self, source: RemoteSource):
        with patch.object(
            async_cache, "hget", new_callable=AsyncMock, return_value=None
        ):
            result = await source.get_rom(
                "nonexistent game", "nes", assume_cache_present=True
            )
        assert result is None

    async def test_empty_filename_returns_none(self, source: RemoteSource):
        result = await source.get_rom("", "nes", assume_cache_present=True)
        assert result is None


class TestRemoteSourceGetMameEntry:
    @pytest.fixture
    def source(self) -> RemoteSource:
        return RemoteSource()

    async def test_cache_miss_returns_none(self, source: RemoteSource):
        with patch.object(
            async_cache, "hget", new_callable=AsyncMock, return_value=None
        ):
            result = await source.get_mame_entry("pacman.zip")
        assert result is None

    async def test_cache_hit_returns_dict(self, source: RemoteSource):
        # Real LaunchBox Mame.xml indexes by stem (e.g. `wrlok_l3`, no ext)
        # and carries `<Name>` as the full title.
        mame_entry = {
            "FileName": "wrlok_l3",
            "Name": "Warlok",
            "Year": "1982",
        }
        with patch.object(
            async_cache,
            "hget",
            new_callable=AsyncMock,
            return_value=json.dumps(mame_entry),
        ) as mock_hget:
            result = await source.get_mame_entry("wrlok_l3")
        mock_hget.assert_called_once_with(LAUNCHBOX_MAME_KEY, "wrlok_l3")
        assert result == mame_entry

    async def test_falls_back_to_stem_when_given_filename_with_ext(
        self, source: RemoteSource
    ):
        mame_entry = {"FileName": "wrlok_l3", "Name": "Warlok"}

        async def fake_hget(_key, field):
            return json.dumps(mame_entry) if field == "wrlok_l3" else None

        with patch.object(
            async_cache, "hget", new_callable=AsyncMock, side_effect=fake_hget
        ) as mock_hget:
            result = await source.get_mame_entry("wrlok_l3.zip")
        # First lookup by raw filename (miss), then by stem (hit).
        assert mock_hget.call_count == 2
        assert mock_hget.call_args_list[0].args == (LAUNCHBOX_MAME_KEY, "wrlok_l3.zip")
        assert mock_hget.call_args_list[1].args == (LAUNCHBOX_MAME_KEY, "wrlok_l3")
        assert result == mame_entry

    async def test_empty_input_returns_none(self, source: RemoteSource):
        result = await source.get_mame_entry("")
        assert result is None

    async def test_whitespace_stripped(self, source: RemoteSource):
        with patch.object(
            async_cache, "hget", new_callable=AsyncMock, return_value=None
        ) as mock_hget:
            await source.get_mame_entry("  wrlok_l3  ")
        # First call uses the trimmed filename.
        assert mock_hget.call_args_list[0].args == (LAUNCHBOX_MAME_KEY, "wrlok_l3")


class TestRemoteSourceFetchImages:
    @pytest.fixture
    def source(self) -> RemoteSource:
        return RemoteSource()

    async def test_remote_disabled_returns_none(self, source: RemoteSource):
        result = await source.fetch_images(remote_enabled=False)
        assert result is None

    async def test_no_id_returns_none(self, source: RemoteSource):
        result = await source.fetch_images(remote=None, database_id=None)
        assert result is None

    async def test_id_from_database_id_arg(self, source: RemoteSource):
        with patch.object(
            async_cache,
            "hget",
            new_callable=AsyncMock,
            return_value=json.dumps(REMOTE_IMAGES),
        ) as mock_hget:
            result = await source.fetch_images(database_id=1234)
        mock_hget.assert_called_once_with(LAUNCHBOX_METADATA_IMAGE_KEY, "1234")
        assert result == REMOTE_IMAGES

    async def test_id_from_remote_dict(self, source: RemoteSource):
        with patch.object(
            async_cache,
            "hget",
            new_callable=AsyncMock,
            return_value=json.dumps(REMOTE_IMAGES),
        ) as mock_hget:
            result = await source.fetch_images(remote={"DatabaseID": "1234"})
        mock_hget.assert_called_once_with(LAUNCHBOX_METADATA_IMAGE_KEY, "1234")
        assert result == REMOTE_IMAGES

    async def test_cache_miss_returns_none(self, source: RemoteSource):
        with patch.object(
            async_cache, "hget", new_callable=AsyncMock, return_value=None
        ):
            result = await source.fetch_images(database_id=9999)
        assert result is None


# ===========================================================================
# TestBuildLaunchboxMetadata
# ===========================================================================


class TestBuildLaunchboxMetadata:
    def test_local_only(self):
        local = {
            "ReleaseDate": "1985-09-13",
            "MaxPlayers": "2",
            "Genre": "Platformer",
            "Publisher": "Nintendo",
            "Developer": "Nintendo",
            "PlayMode": "Single Player",
            "CommunityStarRating": "4.0",
            "CommunityStarRatingTotalVotes": "500",
        }
        meta = build_launchbox_metadata(local=local, remote=None, images=[])
        assert meta.get("max_players", None) == 2
        assert meta.get("genres", []) == ["Platformer"]
        assert "Nintendo" in meta.get("companies", [])
        assert meta.get("cooperative", None) is False

    def test_remote_only(self):
        meta = build_launchbox_metadata(local=None, remote=REMOTE_ENTRY, images=[])
        assert meta.get("max_players", None) == 2
        assert meta.get("genres", []) == ["Platformer"]
        assert meta.get("community_rating", None) == 4.5
        assert meta.get("community_rating_count", None) == 1000

    def test_local_takes_precedence_over_remote(self):
        local = {"MaxPlayers": "4", "Genre": "RPG"}
        remote = {"MaxPlayers": "1", "Genres": "Platformer"}
        meta = build_launchbox_metadata(local=local, remote=remote, images=[])
        assert meta.get("max_players", None) == 4
        assert meta.get("genres", []) == ["RPG"]

    def test_release_date_parsed(self):
        local = {"ReleaseDate": "1985-09-13T00:00:00"}
        meta = build_launchbox_metadata(local=local, remote=None, images=[])
        assert isinstance(meta["first_release_date"], int)
        assert meta["first_release_date"] > 0

    def test_esrb_stripped(self):
        remote = {**REMOTE_ENTRY, "ESRB": "E - Everyone"}
        meta = build_launchbox_metadata(local=None, remote=remote, images=[])
        assert meta.get("esrb", None) == "E"

    def test_cooperative_from_playmode(self):
        local = {"PlayMode": "Cooperative"}
        meta = build_launchbox_metadata(local=local, remote=None, images=[])
        assert meta.get("cooperative", None) is True

    def test_youtube_video_id_extracted(self):
        local = {"VideoUrl": "https://www.youtube.com/watch?v=abc123"}
        meta = build_launchbox_metadata(local=local, remote=None, images=[])
        assert meta.get("youtube_video_id", None) == "abc123"

    def test_companies_deduplicated(self):
        local = {"Developer": "Nintendo", "Publisher": "Nintendo"}
        meta = build_launchbox_metadata(local=local, remote=None, images=[])
        assert meta.get("companies", []) == ["Nintendo"]

    def test_images_passed_through(self):
        images = [
            LaunchboxImage(
                url="https://images.launchbox-app.com/cover.png", type="Box - Front"
            )
        ]
        meta = build_launchbox_metadata(local=None, remote=None, images=images)
        assert meta.get("images", []) == images


class TestGetVideo:
    @pytest.fixture
    def videos_dir(self, tmp_path: Path, monkeypatch) -> Path:
        videos_root = tmp_path / "Videos"
        videos_root.mkdir()
        monkeypatch.setattr(
            "handler.metadata.launchbox_handler.media.LAUNCHBOX_VIDEOS_DIR",
            videos_root,
        )
        # file_uri_for_local_path is rooted at LAUNCHBOX_LOCAL_DIR: patch so our
        # tmp videos sit under it and produce a well-formed URL.
        monkeypatch.setattr(
            "handler.metadata.launchbox_handler.utils.LAUNCHBOX_LOCAL_DIR",
            tmp_path,
        )
        return videos_root

    def _req(
        self, fs_name: str, title: str = "", platform: str = "NES"
    ) -> MediaRequest:
        return MediaRequest(
            platform_name=platform,
            fs_name=fs_name,
            title=title,
            region_hint=None,
            remote_images=None,
            remote_enabled=False,
        )

    def test_no_platform_returns_none(self, videos_dir: Path):
        req = MediaRequest(
            platform_name=None,
            fs_name="game.nes",
            title="",
            region_hint=None,
            remote_images=None,
            remote_enabled=False,
        )
        assert _get_video(req) is None

    def test_missing_platform_dir_returns_none(self, videos_dir: Path):
        # videos_dir has no "NES" subdirectory
        assert _get_video(self._req("mario.nes")) is None

    def test_finds_mp4_by_fs_stem(self, videos_dir: Path):
        platform_dir = videos_dir / "NES"
        platform_dir.mkdir()
        (platform_dir / "Mario.mp4").write_bytes(b"")

        url = _get_video(self._req("Mario.nes"))
        assert url == "launchbox-file://Videos/NES/Mario.mp4"

    def test_falls_back_to_title_stem(self, videos_dir: Path):
        platform_dir = videos_dir / "NES"
        platform_dir.mkdir()
        (platform_dir / "Super Mario Bros.webm").write_bytes(b"")

        url = _get_video(self._req("roms-mario-1.nes", title="Super Mario Bros"))
        assert url == "launchbox-file://Videos/NES/Super Mario Bros.webm"

    def test_multiple_extensions_tried(self, videos_dir: Path):
        platform_dir = videos_dir / "NES"
        platform_dir.mkdir()
        (platform_dir / "Mario.mkv").write_bytes(b"")

        url = _get_video(self._req("Mario.nes"))
        assert url is not None
        assert url.endswith(".mkv")

    def test_no_match_returns_none(self, videos_dir: Path):
        platform_dir = videos_dir / "NES"
        platform_dir.mkdir()
        (platform_dir / "Zelda.mp4").write_bytes(b"")

        assert _get_video(self._req("Mario.nes")) is None


class TestPopulateRomSpecificPaths:
    def _rom(self) -> MagicMock:
        rom = MagicMock()
        rom.platform_id = 7
        rom.id = 42
        return rom

    def test_no_video_url_is_noop(self):
        metadata: LaunchboxMetadata = {"first_release_date": None, "images": []}
        with patch(
            "handler.metadata.launchbox_handler.media.get_preferred_media_types"
        ) as mock_preferred:
            from config.config_manager import MetadataMediaType

            mock_preferred.return_value = [MetadataMediaType.VIDEO]
            populate_rom_specific_paths(metadata, self._rom())
        assert "video_path" not in metadata

    def test_video_url_populates_path(self):
        metadata: LaunchboxMetadata = {
            "first_release_date": None,
            "images": [],
            "video_url": "launchbox-file://Videos/NES/Mario.mp4",
        }
        with patch(
            "handler.metadata.launchbox_handler.media.get_preferred_media_types"
        ) as mock_preferred:
            from config.config_manager import MetadataMediaType

            mock_preferred.return_value = [MetadataMediaType.VIDEO]
            populate_rom_specific_paths(metadata, self._rom())
        path = metadata.get("video_path", "")
        assert path.endswith("/video.mp4")
        assert "7" in path and "42" in path

    def test_video_path_preserves_source_extension(self):
        from config.config_manager import MetadataMediaType

        for src_ext, expected in (
            (".mkv", "/video.mkv"),
            (".webm", "/video.webm"),
            (".MOV", "/video.mov"),
        ):
            metadata: LaunchboxMetadata = {
                "first_release_date": None,
                "images": [],
                "video_url": f"launchbox-file://Videos/NES/Mario{src_ext}",
            }
            with patch(
                "handler.metadata.launchbox_handler.media.get_preferred_media_types"
            ) as mock_preferred:
                mock_preferred.return_value = [MetadataMediaType.VIDEO]
                populate_rom_specific_paths(metadata, self._rom())
            assert metadata.get("video_path", "").endswith(expected)

    def test_video_not_in_preferred_media_skips(self):
        metadata: LaunchboxMetadata = {
            "first_release_date": None,
            "images": [],
            "video_url": "launchbox-file://Videos/NES/Mario.mp4",
        }
        with patch(
            "handler.metadata.launchbox_handler.media.get_preferred_media_types"
        ) as mock_preferred:
            mock_preferred.return_value = []
            populate_rom_specific_paths(metadata, self._rom())
        assert "video_path" not in metadata


class TestRemoteMediaReq:
    def test_explicit_platform_name_wins(self):
        req = remote_media_req(
            remote={"Name": "Super Mario Bros.", "Platform": "Wii"},
            remote_images=None,
            remote_enabled=True,
            platform_name="Nintendo Entertainment System",
            fs_name="mario.nes",
        )
        assert req.platform_name == "Nintendo Entertainment System"
        assert req.fs_name == "mario.nes"
        assert req.title == "Super Mario Bros."

    def test_falls_back_to_remote_platform(self):
        req = remote_media_req(
            remote={"Name": "H.E.R.O.", "Platform": "Atari 2600"},
            remote_images=None,
            remote_enabled=True,
        )
        assert req.platform_name == "Atari 2600"
        assert req.fs_name == ""
        assert req.title == "H.E.R.O."

    def test_no_platform_available_is_none(self):
        req = remote_media_req(
            remote={"Name": "Some Game"},
            remote_images=None,
            remote_enabled=True,
        )
        assert req.platform_name is None


class TestRemoteMatchLocalImages:
    """Regression test for bug where remote-matched roms skipped local image lookup.

    When a ROM matches only via the remote Metadata.xml (no local XML entry),
    the handler previously passed platform_name=None to remote_media_req, which
    caused _build_local_media_context to bail and never search on-disk images.
    """

    async def test_remote_match_finds_local_images(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        # Arrange: images on disk, no local XML match, remote returns a hit.
        # Use "Clear Logo" + "Box - Front" to exercise both _get_images and
        # _get_cover through the same remote-match path.
        lb_root = tmp_path / "launchbox"
        images_root = lb_root / "Images"
        logo_dir = images_root / "Atari 2600" / "Clear Logo"
        box_dir = images_root / "Atari 2600" / "Box - Front"
        logo_dir.mkdir(parents=True)
        box_dir.mkdir(parents=True)
        (logo_dir / "H.E.R.O-01.png").write_bytes(b"")
        (box_dir / "H.E.R.O-01.png").write_bytes(b"")

        monkeypatch.setattr(
            "handler.metadata.launchbox_handler.media.LAUNCHBOX_IMAGES_DIR",
            images_root,
        )
        monkeypatch.setattr(
            "handler.metadata.launchbox_handler.utils.LAUNCHBOX_LOCAL_DIR",
            lb_root,
        )

        h = LaunchboxHandler()
        h._local = MagicMock(spec=LocalSource)
        h._remote = MagicMock(spec=RemoteSource)
        h._local.get_rom = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.get_mame_entry = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.get_rom = AsyncMock(  # type: ignore[method-assign]
            return_value={
                "DatabaseID": "42",
                "Name": "H.E.R.O.",
                "Platform": "Atari 2600",
            }
        )
        h._remote.fetch_images = AsyncMock(return_value=None)  # type: ignore[method-assign]
        monkeypatch.setattr(LaunchboxHandler, "is_enabled", lambda *_: True)
        monkeypatch.setattr(async_cache, "exists", AsyncMock(return_value=True))

        with patch(
            "handler.metadata.launchbox_handler.handler.fs_rom_handler"
        ) as mock_fs:
            mock_fs.get_file_name_with_no_tags.return_value = "hero"
            result = await h.get_rom("hero.a26", "atari2600")

        # Assert: both the clear logo and box-front cover resolved to
        # launchbox-file:// URLs, even though the local XML never matched.
        assert "launchbox_metadata" in result
        images = result["launchbox_metadata"]["images"]
        assert len(images) == 1
        assert "type" in images[0]
        assert "url" in images[0]
        assert images[0]["type"] == "Clear Logo"
        assert images[0]["url"] == (
            "launchbox-file://Images/Atari 2600/Clear Logo/H.E.R.O-01.png"
        )
        assert "url_cover" in result
        assert result["url_cover"] == (
            "launchbox-file://Images/Atari 2600/Box - Front/H.E.R.O-01.png"
        )


class TestBuildRom:
    def test_name_from_local_title(self):
        local = {"Title": "Super Mario Bros.", "Notes": "Classic platformer"}
        rom = build_rom(local=local, remote=None, launchbox_id=1234)
        assert rom.get("name", None) == "Super Mario Bros."
        assert rom.get("summary", None) == "Classic platformer"
        assert rom.get("launchbox_id", None) == 1234

    def test_name_falls_back_to_remote(self):
        rom = build_rom(local=None, remote=REMOTE_ENTRY, launchbox_id=1234)
        assert rom.get("name", None) == "Super Mario Bros."
        assert rom.get("summary", None) == "Jump and run platformer by Nintendo."

    def test_local_name_overrides_remote(self):
        local = {"Title": "Local Title", "Notes": "Local Notes"}
        rom = build_rom(local=local, remote=REMOTE_ENTRY, launchbox_id=1234)
        assert rom.get("name", None) == "Local Title"
        assert rom.get("summary", None) == "Local Notes"

    def test_no_media_req_yields_empty_media(self):
        rom = build_rom(
            local=None, remote=REMOTE_ENTRY, launchbox_id=1234, media_req=None
        )
        assert rom.get("url_cover", None) == ""
        assert rom.get("url_screenshots", None) == []
        assert rom.get("url_manual", None) == ""

    def test_launchbox_id_set(self):
        rom = build_rom(local=None, remote=REMOTE_ENTRY, launchbox_id=42)
        assert rom.get("launchbox_id", None) == 42


# ===========================================================================
# TestLaunchboxHandler
# ===========================================================================


class TestLaunchboxHandlerEnabled:
    def test_is_cloud_enabled_true(self):
        with patch(
            "handler.metadata.launchbox_handler.handler.LAUNCHBOX_API_ENABLED", True
        ):
            assert LaunchboxHandler.is_cloud_enabled() is True

    def test_is_cloud_enabled_false(self):
        with patch(
            "handler.metadata.launchbox_handler.handler.LAUNCHBOX_API_ENABLED", False
        ):
            assert LaunchboxHandler.is_cloud_enabled() is False

    def test_is_local_enabled_true(self, tmp_path: Path):
        platforms = tmp_path / "Data" / "Platforms"
        platforms.mkdir(parents=True)
        with patch(
            "handler.metadata.launchbox_handler.handler.LAUNCHBOX_PLATFORMS_DIR",
            platforms,
        ):
            assert LaunchboxHandler.is_local_enabled() is True

    def test_is_local_enabled_false(self):
        with patch(
            "handler.metadata.launchbox_handler.handler.LAUNCHBOX_PLATFORMS_DIR",
            Path("/does/not/exist"),
        ):
            assert LaunchboxHandler.is_local_enabled() is False

    def test_is_enabled_true_when_cloud(self):
        with patch.object(LaunchboxHandler, "is_cloud_enabled", return_value=True):
            with patch.object(LaunchboxHandler, "is_local_enabled", return_value=False):
                assert LaunchboxHandler.is_enabled() is True

    def test_is_enabled_true_when_local(self):
        with patch.object(LaunchboxHandler, "is_cloud_enabled", return_value=False):
            with patch.object(LaunchboxHandler, "is_local_enabled", return_value=True):
                assert LaunchboxHandler.is_enabled() is True

    def test_is_enabled_false_when_both_off(self):
        with patch.object(LaunchboxHandler, "is_cloud_enabled", return_value=False):
            with patch.object(LaunchboxHandler, "is_local_enabled", return_value=False):
                assert LaunchboxHandler.is_enabled() is False


class TestLaunchboxHandlerGetPlatform:
    def test_delegates_to_get_platform(self):
        handler = LaunchboxHandler()
        p = handler.get_platform("nes")
        assert p.get("launchbox_id", None) == 27

    def test_unknown_platform(self):
        handler = LaunchboxHandler()
        p = handler.get_platform("totally-unknown")
        assert p["launchbox_id"] is None


class TestLaunchboxHandlerGetRom:
    @pytest.fixture
    def handler(self, monkeypatch) -> LaunchboxHandler:
        h = LaunchboxHandler()
        h._local = MagicMock(spec=LocalSource)
        h._remote = MagicMock(spec=RemoteSource)
        h._local.get_rom = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.get_rom = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.get_by_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.get_mame_entry = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.fetch_images = AsyncMock(return_value=None)  # type: ignore[method-assign]
        monkeypatch.setattr(LaunchboxHandler, "is_enabled", lambda *_: True)
        monkeypatch.setattr(async_cache, "exists", AsyncMock(return_value=True))
        return h

    async def test_disabled_returns_fallback(
        self, handler: LaunchboxHandler, monkeypatch
    ):
        monkeypatch.setattr(LaunchboxHandler, "is_enabled", lambda *_: False)
        result = await handler.get_rom("game.nes", "nes")
        assert result["launchbox_id"] is None

    async def test_local_found_remote_unavailable(
        self, handler: LaunchboxHandler, monkeypatch
    ):
        local_data = {"Title": "Mario", "DatabaseID": "1234"}
        monkeypatch.setattr(async_cache, "exists", AsyncMock(return_value=False))
        with patch.object(
            handler._local, "get_rom", new=AsyncMock(return_value=local_data)
        ):
            result = await handler.get_rom("game.nes", "nes")

        assert result.get("launchbox_id", None) == 1234
        assert result.get("name", None) == "Mario"

    async def test_local_found_supplements_remote_by_id(
        self, handler: LaunchboxHandler
    ):
        local_data = {"Title": "Mario", "DatabaseID": "1234"}
        mock_get_by_id = AsyncMock(return_value=REMOTE_ENTRY)
        with (
            patch.object(
                handler._local, "get_rom", new=AsyncMock(return_value=local_data)
            ),
            patch.object(handler._remote, "get_by_id", new=mock_get_by_id),
        ):
            result = await handler.get_rom("game.nes", "nes")

        mock_get_by_id.assert_called_once_with(1234)
        assert result.get("launchbox_id", None) == 1234

    async def test_local_found_supplements_remote_by_title_fallback(
        self, handler: LaunchboxHandler
    ):
        local_data = {"Title": "Mario"}  # no DatabaseID
        mock_get_rom = AsyncMock(return_value=REMOTE_ENTRY)
        with (
            patch.object(
                handler._local, "get_rom", new=AsyncMock(return_value=local_data)
            ),
            patch.object(handler._remote, "get_rom", new=mock_get_rom),
        ):
            result = await handler.get_rom("game.nes", "nes")

        mock_get_rom.assert_called_once_with("Mario", "nes", assume_cache_present=True)
        assert result.get("name", None) == "Mario"

    async def test_no_local_no_remote_returns_fallback(
        self, handler: LaunchboxHandler, monkeypatch
    ):
        monkeypatch.setattr(async_cache, "exists", AsyncMock(return_value=False))
        result = await handler.get_rom("game.nes", "nes")
        assert result["launchbox_id"] is None

    async def test_tag_in_filename_matches_by_id(self, handler: LaunchboxHandler):
        with patch.object(
            handler._remote, "get_by_id", new=AsyncMock(return_value=REMOTE_ENTRY)
        ):
            result = await handler.get_rom(
                "Super Mario Bros (launchbox-1234).nes", "nes"
            )

        assert result.get("launchbox_id", None) == 1234

    async def test_tag_in_filename_not_found_falls_through_to_name_search(
        self, handler: LaunchboxHandler
    ):
        with (
            patch.object(
                handler._remote,
                "get_rom",
                new=AsyncMock(return_value=REMOTE_ENTRY),
            ),
            patch(
                "handler.metadata.launchbox_handler.handler.fs_rom_handler"
            ) as mock_fs,
        ):
            # fs_rom_handler.get_file_name_with_no_tags strips the tag
            mock_fs.get_file_name_with_no_tags.return_value = "Super Mario Bros"
            result = await handler.get_rom(
                "Super Mario Bros (launchbox-9999).nes", "nes"
            )

        # Falls through to name search, which succeeds
        assert result.get("launchbox_id", None) == 1234

    async def test_name_search_succeeds(self, handler: LaunchboxHandler):
        with (
            patch.object(
                handler._remote,
                "get_rom",
                new=AsyncMock(return_value=REMOTE_ENTRY),
            ),
            patch(
                "handler.metadata.launchbox_handler.handler.fs_rom_handler"
            ) as mock_fs,
        ):
            mock_fs.get_file_name_with_no_tags.return_value = "Super Mario Bros."
            result = await handler.get_rom("Super Mario Bros.nes", "nes")

        assert result.get("launchbox_id", None) == 1234
        assert result.get("name", None) == "Super Mario Bros."

    async def test_name_search_fails_returns_fallback(self, handler: LaunchboxHandler):
        with patch(
            "handler.metadata.launchbox_handler.handler.fs_rom_handler"
        ) as mock_fs:
            mock_fs.get_file_name_with_no_tags.return_value = "Unknown Game"
            result = await handler.get_rom("Unknown Game.nes", "nes")
        assert result["launchbox_id"] is None

    async def test_keep_tags_true_skips_tag_stripping(self, handler: LaunchboxHandler):
        with patch(
            "handler.metadata.launchbox_handler.handler.fs_rom_handler"
        ) as mock_fs:
            await handler.get_rom("Game (USA).nes", "nes", keep_tags=True)
            # fs_rom_handler.get_file_name_with_no_tags should NOT be called
            mock_fs.get_file_name_with_no_tags.assert_not_called()

    async def test_arcade_mame_resolves_shortname_to_full_title(
        self, handler: LaunchboxHandler
    ):
        mame_entry = {"FileName": "wrlok_l3", "Name": "Warlok"}
        remote_entry = {"DatabaseID": "999", "Name": "Warlok"}
        with (
            patch.object(
                handler._remote,
                "get_mame_entry",
                new=AsyncMock(return_value=mame_entry),
            ) as mock_mame,
            patch.object(
                handler._remote,
                "get_rom",
                new=AsyncMock(return_value=remote_entry),
            ) as mock_get_rom,
            patch(
                "handler.metadata.launchbox_handler.handler.fs_rom_handler"
            ) as mock_fs,
        ):
            mock_fs.get_file_name_with_no_tags.return_value = "wrlok_l3"
            result = await handler.get_rom("wrlok_l3.zip", "arcade")

        mock_mame.assert_called_once_with("wrlok_l3.zip")
        # Search term should be the MAME Name, lowercased.
        assert mock_get_rom.call_args.args[0] == "warlok"
        assert result.get("name", None) == "Warlok"
        assert result.get("launchbox_id", None) == 999

    async def test_arcade_mame_miss_falls_back_to_filename_search(
        self, handler: LaunchboxHandler
    ):
        with (
            patch.object(
                handler._remote,
                "get_mame_entry",
                new=AsyncMock(return_value=None),
            ) as mock_mame,
            patch(
                "handler.metadata.launchbox_handler.handler.fs_rom_handler"
            ) as mock_fs,
        ):
            mock_fs.get_file_name_with_no_tags.return_value = "wrlok_l3"
            result = await handler.get_rom("wrlok_l3.zip", "arcade")

        mock_mame.assert_called_once_with("wrlok_l3.zip")
        assert result["launchbox_id"] is None

    async def test_arcade_mame_only_match_sets_fallback_name(
        self, handler: LaunchboxHandler
    ):
        # MAME entry exists but Metadata.xml has no matching game: still surface
        # the MAME name as the rom name.
        mame_entry = {"FileName": "wrlok_l3", "Name": "Warlok"}
        with (
            patch.object(
                handler._remote,
                "get_mame_entry",
                new=AsyncMock(return_value=mame_entry),
            ),
            patch(
                "handler.metadata.launchbox_handler.handler.fs_rom_handler"
            ) as mock_fs,
        ):
            mock_fs.get_file_name_with_no_tags.return_value = "wrlok_l3"
            result = await handler.get_rom("wrlok_l3.zip", "arcade")

        assert result["launchbox_id"] is None
        assert result.get("name", None) == "Warlok"

    async def test_non_arcade_platform_skips_mame_lookup(
        self, handler: LaunchboxHandler
    ):
        with (
            patch.object(
                handler._remote, "get_mame_entry", new=AsyncMock()
            ) as mock_mame,
            patch(
                "handler.metadata.launchbox_handler.handler.fs_rom_handler"
            ) as mock_fs,
        ):
            mock_fs.get_file_name_with_no_tags.return_value = "wrlok_l3"
            await handler.get_rom("wrlok_l3.zip", "nes")

        mock_mame.assert_not_called()


class TestLaunchboxHandlerGetRomById:
    @pytest.fixture
    def handler(self, monkeypatch) -> LaunchboxHandler:
        h = LaunchboxHandler()
        h._remote = MagicMock(spec=RemoteSource)
        h._remote.get_by_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.fetch_images = AsyncMock(return_value=None)  # type: ignore[method-assign]
        monkeypatch.setattr(LaunchboxHandler, "is_enabled", lambda *_: True)
        return h

    async def test_disabled_returns_fallback(
        self, handler: LaunchboxHandler, monkeypatch
    ):
        monkeypatch.setattr(LaunchboxHandler, "is_enabled", lambda *_: False)
        result = await handler.get_rom_by_id(1234)
        assert result["launchbox_id"] is None

    async def test_remote_disabled_returns_fallback(self, handler: LaunchboxHandler):
        result = await handler.get_rom_by_id(1234, remote_enabled=False)
        assert result["launchbox_id"] is None

    async def test_not_in_cache_returns_fallback(self, handler: LaunchboxHandler):
        result = await handler.get_rom_by_id(9999)
        assert result["launchbox_id"] is None

    async def test_found_returns_launchbox_rom(self, handler: LaunchboxHandler):
        with (
            patch.object(
                handler._remote,
                "get_by_id",
                new=AsyncMock(return_value=REMOTE_ENTRY),
            ),
            patch.object(
                handler._remote,
                "fetch_images",
                new=AsyncMock(return_value=REMOTE_IMAGES),
            ),
        ):
            result = await handler.get_rom_by_id(1234)

        assert result.get("launchbox_id", None) == 1234
        assert result.get("name", None) == "Super Mario Bros."
        assert result.get("launchbox_metadata") is not None


class TestLaunchboxHandlerSearch:
    @pytest.fixture
    def handler(self, monkeypatch) -> LaunchboxHandler:
        h = LaunchboxHandler()
        h._local = MagicMock(spec=LocalSource)
        h._remote = MagicMock(spec=RemoteSource)
        h._local.get_rom = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.get_rom = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.get_by_id = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.get_mame_entry = AsyncMock(return_value=None)  # type: ignore[method-assign]
        h._remote.fetch_images = AsyncMock(return_value=None)  # type: ignore[method-assign]
        monkeypatch.setattr(LaunchboxHandler, "is_enabled", lambda *_: True)
        monkeypatch.setattr(async_cache, "exists", AsyncMock(return_value=True))
        return h

    async def test_get_matched_roms_by_name_disabled_returns_empty(
        self, handler: LaunchboxHandler, monkeypatch
    ):
        monkeypatch.setattr(LaunchboxHandler, "is_enabled", lambda *_: False)
        result = await handler.get_matched_roms_by_name("Mario", "nes")
        assert result == []

    async def test_get_matched_roms_by_name_found(self, handler: LaunchboxHandler):
        with patch.object(
            handler._remote, "get_rom", new=AsyncMock(return_value=REMOTE_ENTRY)
        ):
            result = await handler.get_matched_roms_by_name("Super Mario Bros.", "nes")

        assert len(result) == 1
        assert result[0].get("launchbox_id", 0) == 1234

    async def test_get_matched_rom_by_id_disabled_returns_none(
        self, handler: LaunchboxHandler, monkeypatch
    ):
        monkeypatch.setattr(LaunchboxHandler, "is_enabled", lambda *_: False)
        result = await handler.get_matched_rom_by_id(1234)
        assert result is None

    async def test_get_matched_rom_by_id_found(self, handler: LaunchboxHandler):
        with patch.object(
            handler._remote, "get_by_id", new=AsyncMock(return_value=REMOTE_ENTRY)
        ):
            result = await handler.get_matched_rom_by_id(1234)
        assert result is not None
        assert result.get("launchbox_id", None) == 1234

    async def test_get_matched_rom_by_id_not_found_returns_none(
        self, handler: LaunchboxHandler
    ):
        result = await handler.get_matched_rom_by_id(9999)
        assert result is None
