from types import SimpleNamespace
from unittest.mock import patch

from handler.scan_handler import (
    MetadataSource,
    get_priority_ordered_metadata_sources,
    scene_apply_sources,
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


def test_scene_match_drops_similar_game_sources():
    """Demozoo/Pouët must not inherit a similarly titled game's box art."""
    available = [
        MetadataSource.IGDB,
        MetadataSource.MOBY,
        MetadataSource.DEMOZOO,
        MetadataSource.POUET,
        MetadataSource.SS,
    ]
    assert scene_apply_sources(available) == [
        MetadataSource.DEMOZOO,
        MetadataSource.POUET,
    ]


def test_csdb_only_still_locks():
    available = [MetadataSource.IGDB, MetadataSource.CSDB]
    assert scene_apply_sources(available) == [MetadataSource.CSDB]


def test_scene_lock_is_a_no_op_for_regular_games():
    """Games without a Demozoo/Pouët id keep fuzzy catalog matching."""
    available = [MetadataSource.IGDB, MetadataSource.MOBY, MetadataSource.SS]
    assert scene_apply_sources(available) == available


def test_pouet_only_still_locks():
    available = [MetadataSource.IGDB, MetadataSource.POUET]
    assert scene_apply_sources(available) == [MetadataSource.POUET]


def test_persisted_scene_lock_survives_an_empty_scene_lookup():
    """An unreachable provider must not hand a known production to the catalogs."""
    available = [MetadataSource.IGDB, MetadataSource.MOBY]
    assert scene_apply_sources(available, scene_locked=True) == []


def test_scene_lock_keeps_this_scans_match():
    available = [MetadataSource.IGDB, MetadataSource.DEMOZOO]
    assert scene_apply_sources(available, scene_locked=True) == [MetadataSource.DEMOZOO]
