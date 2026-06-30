"""Unit tests for the data-transform helpers of migration 0092.

The migration module name starts with a digit, so it is loaded by path rather
than imported directly. Only the pure helpers are exercised here; the row
iteration runs against a live DB in CI's alembic upgrade.
"""

import importlib.util
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0092_strip_ss_media_urls.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_0092", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _load_migration()


class TestIsScreenscraperUrl:
    def test_screenscraper_host(self, migration):
        assert migration._is_screenscraper_url(
            "https://api.screenscraper.fr/api2/mediaJeu.php?media=box-2D(wor)"
        )

    def test_subdomain(self, migration):
        assert migration._is_screenscraper_url("https://www.screenscraper.fr/img.png")

    def test_non_screenscraper_host(self, migration):
        url = "https://images.igdb.com/igdb/image/upload/t_cover_big/co1234.jpg"
        assert not migration._is_screenscraper_url(url)

    def test_lookalike_host(self, migration):
        # Suffix attack must not be treated as ScreenScraper
        assert not migration._is_screenscraper_url(
            "https://screenscraper.fr.evil.example/img.png"
        )

    def test_empty_and_none(self, migration):
        assert not migration._is_screenscraper_url("")
        assert not migration._is_screenscraper_url(None)


class TestCleanSsMetadata:
    def test_removes_url_keys_keeps_rest(self, migration):
        ss_metadata = {
            "box2d_url": "https://screenscraper.fr/box.png",
            "box2d_path": "roms/1/1/box2d.png",
            "screenshot_url": "https://screenscraper.fr/ss.png",
            "video_normalized_url": "https://screenscraper.fr/v.mp4",
            "ss_score": "8.0",
            "genres": ["Action"],
        }
        cleaned = migration._clean_ss_metadata(ss_metadata)
        assert cleaned == {
            "box2d_path": "roms/1/1/box2d.png",
            "ss_score": "8.0",
            "genres": ["Action"],
        }

    def test_empty_dict_unchanged(self, migration):
        assert migration._clean_ss_metadata({}) == {}

    def test_none_passthrough(self, migration):
        assert migration._clean_ss_metadata(None) is None
