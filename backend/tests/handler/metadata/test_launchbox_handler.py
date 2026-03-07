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

from handler.metadata.launchbox_handler.handler import LaunchboxHandler
from handler.metadata.launchbox_handler.local_source import LocalSource
from handler.metadata.launchbox_handler.media import build_launchbox_metadata, build_rom
from handler.metadata.launchbox_handler.platforms import get_platform
from handler.metadata.launchbox_handler.remote_source import RemoteSource
from handler.metadata.launchbox_handler.types import (
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    LaunchboxImage,
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
            with patch.object(
                async_cache, "hget", new_callable=AsyncMock, return_value=None
            ):
                with patch.object(async_cache, "hset", new_callable=AsyncMock):
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
            with patch.object(
                async_cache, "hget", new_callable=AsyncMock, return_value=None
            ):
                with patch.object(async_cache, "hset", new_callable=AsyncMock):
                    # "Mega Man 2.nes" → stem "Mega Man 2" → title key "mega man 2"
                    result = await source.get_rom("Mega Man 2.nes", "nes")

        assert result is not None
        assert result.get("Title", None) == "Mega Man 2"

    async def test_cache_hit_uses_cached_index(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        mtime_ns = (await AnyioPath(str(nes_xml)).stat()).st_mtime_ns
        cached_index = {
            "super mario bros..nes": {"Title": "Cached Entry", "DatabaseID": "9999"}
        }
        cached_payload = json.dumps((mtime_ns, cached_index))

        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            with patch.object(
                async_cache, "hget", new_callable=AsyncMock, return_value=cached_payload
            ):
                with patch.object(
                    async_cache, "hset", new_callable=AsyncMock
                ) as mock_hset:
                    result = await source.get_rom("super mario bros..nes", "nes")
                    # hset should NOT be called — we used the cache
                    mock_hset.assert_not_called()

        assert result is not None
        assert result.get("Title", None) == "Cached Entry"

    async def test_stale_cache_triggers_reparse(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        stale_mtime = 0  # clearly wrong mtime
        stale_index = {"super mario bros..nes": {"Title": "Stale Entry"}}
        stale_payload = json.dumps((stale_mtime, stale_index))

        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            with patch.object(
                async_cache, "hget", new_callable=AsyncMock, return_value=stale_payload
            ):
                with patch.object(
                    async_cache, "hset", new_callable=AsyncMock
                ) as mock_hset:
                    result = await source.get_rom("super mario bros..nes", "nes")
                    # hset should be called with fresh data
                    mock_hset.assert_called_once()

        # Should return fresh parsed data, not stale entry
        assert result is not None
        assert result.get("Title", None) == "Super Mario Bros."

    async def test_parse_error_returns_none(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        await AnyioPath(str(nes_xml)).write_text("<<<not valid xml>>>")

        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            with patch.object(
                async_cache, "hget", new_callable=AsyncMock, return_value=None
            ):
                with patch.object(async_cache, "hset", new_callable=AsyncMock):
                    result = await source.get_rom("super mario bros..nes", "nes")

        assert result is None

    async def test_empty_fs_name_returns_none(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            with patch.object(
                async_cache, "hget", new_callable=AsyncMock, return_value=None
            ):
                with patch.object(async_cache, "hset", new_callable=AsyncMock):
                    result = await source.get_rom("   ", "nes")

        assert result is None

    async def test_no_match_returns_none(
        self, source: LocalSource, nes_xml: Path, platforms_dir: Path
    ):
        with patch(
            "handler.metadata.launchbox_handler.local_source.LAUNCHBOX_PLATFORMS_DIR",
            platforms_dir,
        ):
            with patch.object(
                async_cache, "hget", new_callable=AsyncMock, return_value=None
            ):
                with patch.object(async_cache, "hset", new_callable=AsyncMock):
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
    def handler(self) -> LaunchboxHandler:
        h = LaunchboxHandler()
        h._local = MagicMock(spec=LocalSource)
        h._remote = MagicMock(spec=RemoteSource)
        return h

    async def test_disabled_returns_fallback(self, handler: LaunchboxHandler):
        with patch.object(LaunchboxHandler, "is_enabled", return_value=False):
            result = await handler.get_rom("game.nes", "nes")
        assert result["launchbox_id"] is None

    async def test_local_found_remote_unavailable(self, handler: LaunchboxHandler):
        local_data = {"Title": "Mario", "DatabaseID": "1234"}
        handler._local.get_rom = AsyncMock(return_value=local_data)
        handler._remote.fetch_images = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=False
            ):
                result = await handler.get_rom("game.nes", "nes")

        assert result.get("launchbox_id", None) == 1234
        assert result.get("name", None) == "Mario"

    async def test_local_found_supplements_remote_by_id(
        self, handler: LaunchboxHandler
    ):
        local_data = {"Title": "Mario", "DatabaseID": "1234"}
        handler._local.get_rom = AsyncMock(return_value=local_data)
        handler._remote.get_by_id = AsyncMock(return_value=REMOTE_ENTRY)
        handler._remote.get_rom = AsyncMock(return_value=None)
        handler._remote.fetch_images = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=True
            ):
                result = await handler.get_rom("game.nes", "nes")

        handler._remote.get_by_id.assert_called_once_with(1234)
        assert result.get("launchbox_id", None) == 1234

    async def test_local_found_supplements_remote_by_title_fallback(
        self, handler: LaunchboxHandler
    ):
        local_data = {"Title": "Mario"}  # no DatabaseID
        handler._local.get_rom = AsyncMock(return_value=local_data)
        handler._remote.get_by_id = AsyncMock(return_value=None)
        handler._remote.get_rom = AsyncMock(return_value=REMOTE_ENTRY)
        handler._remote.fetch_images = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=True
            ):
                result = await handler.get_rom("game.nes", "nes")

        handler._remote.get_rom.assert_called_once_with(
            "Mario", "nes", assume_cache_present=True
        )
        assert result.get("name", None) == "Mario"

    async def test_no_local_no_remote_returns_fallback(self, handler: LaunchboxHandler):
        handler._local.get_rom = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=False
            ):
                result = await handler.get_rom("game.nes", "nes")

        assert result["launchbox_id"] is None

    async def test_tag_in_filename_matches_by_id(self, handler: LaunchboxHandler):
        handler._local.get_rom = AsyncMock(return_value=None)
        handler._remote.get_by_id = AsyncMock(return_value=REMOTE_ENTRY)
        handler._remote.fetch_images = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=True
            ):
                result = await handler.get_rom(
                    "Super Mario Bros (launchbox-1234).nes", "nes"
                )

        assert result.get("launchbox_id", None) == 1234

    async def test_tag_in_filename_not_found_falls_through_to_name_search(
        self, handler: LaunchboxHandler
    ):
        handler._local.get_rom = AsyncMock(return_value=None)
        handler._remote.get_by_id = AsyncMock(return_value=None)
        handler._remote.get_rom = AsyncMock(return_value=REMOTE_ENTRY)
        handler._remote.fetch_images = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=True
            ):
                # fs_rom_handler.get_file_name_with_no_tags strips the tag
                with patch(
                    "handler.metadata.launchbox_handler.handler.fs_rom_handler"
                ) as mock_fs:
                    mock_fs.get_file_name_with_no_tags.return_value = "Super Mario Bros"
                    result = await handler.get_rom(
                        "Super Mario Bros (launchbox-9999).nes", "nes"
                    )

        # Falls through to name search, which succeeds
        assert result.get("launchbox_id", None) == 1234

    async def test_name_search_succeeds(self, handler: LaunchboxHandler):
        handler._local.get_rom = AsyncMock(return_value=None)
        handler._remote.get_rom = AsyncMock(return_value=REMOTE_ENTRY)
        handler._remote.fetch_images = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=True
            ):
                with patch(
                    "handler.metadata.launchbox_handler.handler.fs_rom_handler"
                ) as mock_fs:
                    mock_fs.get_file_name_with_no_tags.return_value = (
                        "Super Mario Bros."
                    )
                    result = await handler.get_rom("Super Mario Bros.nes", "nes")

        assert result.get("launchbox_id", None) == 1234
        assert result.get("name", None) == "Super Mario Bros."

    async def test_name_search_fails_returns_fallback(self, handler: LaunchboxHandler):
        handler._local.get_rom = AsyncMock(return_value=None)
        handler._remote.get_rom = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=True
            ):
                with patch(
                    "handler.metadata.launchbox_handler.handler.fs_rom_handler"
                ) as mock_fs:
                    mock_fs.get_file_name_with_no_tags.return_value = "Unknown Game"
                    result = await handler.get_rom("Unknown Game.nes", "nes")

        assert result["launchbox_id"] is None

    async def test_keep_tags_true_skips_tag_stripping(self, handler: LaunchboxHandler):
        handler._local.get_rom = AsyncMock(return_value=None)
        handler._remote.get_rom = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=True
            ):
                with patch(
                    "handler.metadata.launchbox_handler.handler.fs_rom_handler"
                ) as mock_fs:
                    await handler.get_rom("Game (USA).nes", "nes", keep_tags=True)
                    # fs_rom_handler.get_file_name_with_no_tags should NOT be called
                    mock_fs.get_file_name_with_no_tags.assert_not_called()


class TestLaunchboxHandlerGetRomById:
    @pytest.fixture
    def handler(self) -> LaunchboxHandler:
        h = LaunchboxHandler()
        h._remote = MagicMock(spec=RemoteSource)
        return h

    async def test_disabled_returns_fallback(self, handler: LaunchboxHandler):
        with patch.object(LaunchboxHandler, "is_enabled", return_value=False):
            result = await handler.get_rom_by_id(1234)
        assert result["launchbox_id"] is None

    async def test_remote_disabled_returns_fallback(self, handler: LaunchboxHandler):
        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            result = await handler.get_rom_by_id(1234, remote_enabled=False)
        assert result["launchbox_id"] is None

    async def test_not_in_cache_returns_fallback(self, handler: LaunchboxHandler):
        handler._remote.get_by_id = AsyncMock(return_value=None)
        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            result = await handler.get_rom_by_id(9999)
        assert result["launchbox_id"] is None

    async def test_found_returns_launchbox_rom(self, handler: LaunchboxHandler):
        handler._remote.get_by_id = AsyncMock(return_value=REMOTE_ENTRY)
        handler._remote.fetch_images = AsyncMock(return_value=REMOTE_IMAGES)
        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            result = await handler.get_rom_by_id(1234)

        assert result.get("launchbox_id", None) == 1234
        assert result.get("name", None) == "Super Mario Bros."
        assert result.get("launchbox_metadata") is not None


class TestLaunchboxHandlerSearch:
    @pytest.fixture
    def handler(self) -> LaunchboxHandler:
        h = LaunchboxHandler()
        h._local = MagicMock(spec=LocalSource)
        h._remote = MagicMock(spec=RemoteSource)
        return h

    async def test_get_matched_roms_by_name_disabled_returns_empty(
        self, handler: LaunchboxHandler
    ):
        with patch.object(LaunchboxHandler, "is_enabled", return_value=False):
            result = await handler.get_matched_roms_by_name("Mario", "nes")
        assert result == []

    async def test_get_matched_roms_by_name_found(self, handler: LaunchboxHandler):
        handler._local.get_rom = AsyncMock(return_value=None)
        handler._remote.get_rom = AsyncMock(return_value=REMOTE_ENTRY)
        handler._remote.fetch_images = AsyncMock(return_value=None)

        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            with patch.object(
                async_cache, "exists", new_callable=AsyncMock, return_value=True
            ):
                result = await handler.get_matched_roms_by_name(
                    "Super Mario Bros.", "nes"
                )

        assert len(result) == 1
        assert result[0].get("launchbox_id", 0) == 1234

    async def test_get_matched_rom_by_id_disabled_returns_none(
        self, handler: LaunchboxHandler
    ):
        with patch.object(LaunchboxHandler, "is_enabled", return_value=False):
            result = await handler.get_matched_rom_by_id(1234)
        assert result is None

    async def test_get_matched_rom_by_id_found(self, handler: LaunchboxHandler):
        handler._remote.get_by_id = AsyncMock(return_value=REMOTE_ENTRY)
        handler._remote.fetch_images = AsyncMock(return_value=None)
        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            result = await handler.get_matched_rom_by_id(1234)
        assert result is not None
        assert result.get("launchbox_id", None) == 1234

    async def test_get_matched_rom_by_id_not_found_returns_none(
        self, handler: LaunchboxHandler
    ):
        handler._remote.get_by_id = AsyncMock(return_value=None)
        with patch.object(LaunchboxHandler, "is_enabled", return_value=True):
            result = await handler.get_matched_rom_by_id(9999)
        assert result is None
