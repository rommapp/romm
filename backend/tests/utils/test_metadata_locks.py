from unittest.mock import Mock

import pytest

from utils.metadata_locks import (
    METADATA_LOCKABLE_FIELDS,
    PROJECTED_METADATA_LOCK_FIELDS,
    apply_metadata_lock_snapshots,
    effective_metadata_value,
)
from utils.roms_columns import ROMS_METADATA_VIEW_COLUMNS, _locked_metadata_projection


def test_projected_lock_fields_match_the_metadata_view_catalog():
    aliases = {alias for _, alias in ROMS_METADATA_VIEW_COLUMNS}

    assert PROJECTED_METADATA_LOCK_FIELDS <= aliases
    assert PROJECTED_METADATA_LOCK_FIELDS == {
        "genres",
        "franchises",
        "collections",
        "companies",
        "game_modes",
        "age_ratings",
        "first_release_date",
        "player_count",
    }
    assert "publishers" not in PROJECTED_METADATA_LOCK_FIELDS
    assert "developers" not in PROJECTED_METADATA_LOCK_FIELDS
    assert {"name", "summary", "cover", "screenshots", "manual"} <= (
        METADATA_LOCKABLE_FIELDS - PROJECTED_METADATA_LOCK_FIELDS
    )


@pytest.mark.parametrize("pg", [True, False])
def test_only_projected_aliases_receive_lock_expressions(pg: bool):
    for name, alias in ROMS_METADATA_VIEW_COLUMNS:
        plain_expression = f"{name}::text" if pg and alias == "player_count" else name
        plain_projection = f"{plain_expression} AS {alias}"
        projection = _locked_metadata_projection(pg, name, alias, with_locks=True)
        if alias in PROJECTED_METADATA_LOCK_FIELDS:
            assert "metadata_locks" in projection
        else:
            assert projection == plain_projection
        assert (
            _locked_metadata_projection(pg, name, alias, with_locks=False)
            == plain_projection
        )


def test_projected_scalar_casts_and_json_null_handling_are_preserved():
    pg_date = _locked_metadata_projection(
        True, "generated_first_release_date", "first_release_date", with_locks=True
    )
    maria_date = _locked_metadata_projection(
        False, "generated_first_release_date", "first_release_date", with_locks=True
    )
    pg_players = _locked_metadata_projection(
        True, "generated_player_count", "player_count", with_locks=True
    )
    maria_players = _locked_metadata_projection(
        False, "generated_player_count", "player_count", with_locks=True
    )

    assert "(metadata_locks ->> 'first_release_date')::bigint" in pg_date
    assert (
        "CAST(JSON_UNQUOTE(JSON_EXTRACT(metadata_locks, '$.first_release_date')) AS SIGNED)"
        in maria_date
    )
    assert pg_players.endswith("::text AS player_count")
    assert (
        "NULLIF(JSON_UNQUOTE(JSON_EXTRACT(metadata_locks, '$.player_count')), 'null')"
        in maria_players
    )


def test_effective_metadata_value_reads_projected_fields():
    rom = Mock()
    rom.metadatum.genres = ["Locked"]

    assert effective_metadata_value(rom, "genres") == ["Locked"]


def test_apply_metadata_lock_snapshots_only_updates_owned_attributes():
    attrs = {
        "name": "old name",
        "summary": "old summary",
        "url_cover": "old-url",
        "path_cover_s": "old-small",
        "path_cover_l": "old-large",
        "url_screenshots": ["old-shot"],
        "path_screenshots": ["old-path"],
        "url_manual": "old-manual-url",
        "path_manual": "old-manual-path",
        "regions": ["USA"],
    }
    locks = {
        "name": "locked name",
        "cover": {"url": "cover-url", "small": "small.png", "large": "large.png"},
        "screenshots": {"urls": ["shot-url"], "paths": ["shot.png"]},
        "manual": {"url": "manual-url", "path": "manual.pdf"},
    }
    original_locks = {
        key: value.copy() if isinstance(value, dict) else value
        for key, value in locks.items()
    }

    apply_metadata_lock_snapshots(attrs, locks)

    assert attrs == {
        "name": "locked name",
        "summary": "old summary",
        "url_cover": "cover-url",
        "path_cover_s": "small.png",
        "path_cover_l": "large.png",
        "url_screenshots": ["shot-url"],
        "path_screenshots": ["shot.png"],
        "url_manual": "manual-url",
        "path_manual": "manual.pdf",
        "regions": ["USA"],
    }
    assert locks == original_locks
