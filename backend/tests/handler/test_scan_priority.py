from types import SimpleNamespace
from unittest.mock import patch

from handler.scan_handler import (
    MetadataSource,
    get_priority_ordered_metadata_sources,
)


def _fake_config(**overrides):
    return SimpleNamespace(
        SCAN_METADATA_PRIORITY=["igdb", "moby", "ss"],
        SCAN_ARTWORK_PRIORITY=["igdb", "moby", "ss"],
        SCAN_ARTWORK_PRIORITY_OVERRIDES=overrides,
    )


def test_artwork_field_falls_back_to_shared_priority():
    """A field with no override uses SCAN_ARTWORK_PRIORITY."""
    available = [MetadataSource.SS, MetadataSource.IGDB]
    with patch("handler.scan_handler.cm.get_config", return_value=_fake_config()):
        ordered = get_priority_ordered_metadata_sources(available, "url_cover")

    assert ordered == [MetadataSource.IGDB, MetadataSource.SS]


def test_per_field_override_reorders_only_that_field():
    """A cover override wins for url_cover but not for url_screenshots."""
    available = [MetadataSource.IGDB, MetadataSource.SS]
    config = _fake_config(url_cover=["ss", "igdb"])
    with patch("handler.scan_handler.cm.get_config", return_value=config):
        cover = get_priority_ordered_metadata_sources(available, "url_cover")
        screenshots = get_priority_ordered_metadata_sources(
            available, "url_screenshots"
        )

    # Cover honors the override (ss first)...
    assert cover == [MetadataSource.SS, MetadataSource.IGDB]
    # ...while screenshots keep the shared artwork order (igdb first).
    assert screenshots == [MetadataSource.IGDB, MetadataSource.SS]


def test_sources_absent_from_priority_are_appended():
    """Available sources not named in the priority list still appear, last."""
    available = [MetadataSource.SS, MetadataSource.MOBY, MetadataSource.LAUNCHBOX]
    config = _fake_config(url_cover=["ss"])
    with patch("handler.scan_handler.cm.get_config", return_value=config):
        ordered = get_priority_ordered_metadata_sources(available, "url_cover")

    assert ordered[0] == MetadataSource.SS
    assert set(ordered) == set(available)


def test_unknown_override_source_is_ignored_not_fatal():
    """A typo in an override list is dropped, never raising ValueError."""
    available = [MetadataSource.IGDB, MetadataSource.SS]
    config = _fake_config(url_cover=["sss", "igdb"])  # "sss" is a typo
    with patch("handler.scan_handler.cm.get_config", return_value=config):
        ordered = get_priority_ordered_metadata_sources(available, "url_cover")

    assert ordered == [MetadataSource.IGDB, MetadataSource.SS]


def test_metadata_priority_is_unaffected_by_artwork_overrides():
    """Artwork overrides must never leak into the metadata priority pass."""
    available = [MetadataSource.SS, MetadataSource.IGDB]
    config = _fake_config(url_cover=["ss", "igdb"])
    with patch("handler.scan_handler.cm.get_config", return_value=config):
        ordered = get_priority_ordered_metadata_sources(available, "metadata")

    assert ordered == [MetadataSource.IGDB, MetadataSource.SS]
