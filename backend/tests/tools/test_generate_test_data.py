import random
import sys
from collections.abc import Callable
from datetime import datetime, tzinfo
from pathlib import Path
from typing import Any

import pytest
from redis.exceptions import RedisError
from sqlalchemy import event
from tools import generate_test_data

from handler.database import db_rom_handler
from handler.database.base_handler import sync_engine
from handler.metadata.igdb_handler import IGDBMetadata
from handler.metadata.ss_handler import SSMetadata
from models.rom import SEARCH_TITLE_SEPARATOR, Rom, fold_search_title

IMAGE_FIELDS = {"path_cover_s", "path_cover_l", "path_screenshots"}
# Drawn from the per-game metadata stream, or derived from what it draws.
EXTRA_FIELDS = {"igdb_metadata", "ss_metadata", "search_titles"}


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "_FrozenDatetime":
        return cls(2026, 1, 1, 12, 0, tzinfo=tz)


def _rom_rows(
    monkeypatch: pytest.MonkeyPatch,
    resources: Path,
    *flags: str,
    rotate_cache: Callable[[], None] = lambda: None,
    rotate_feeds: Callable[[], None] = lambda: None,
) -> list[dict[str, Any]]:
    """Run the seeder, recording rom rows instead of inserting anything."""
    rows: list[dict[str, Any]] = []

    def record(
        conn: object, model: type, batch: list[dict[str, Any]], chunk: int = 0
    ) -> None:
        if model is Rom:
            rows.extend(batch)

    monkeypatch.setattr(generate_test_data, "bulk_insert", record)
    monkeypatch.setattr(generate_test_data, "_advance_sequences", lambda *_: None)
    monkeypatch.setattr(generate_test_data, "datetime", _FrozenDatetime)
    monkeypatch.setattr(db_rom_handler, "invalidate_filter_values_cache", rotate_cache)
    monkeypatch.setattr(generate_test_data, "invalidate_all_cached_feeds", rotate_feeds)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_test_data.py",
            "--roms", "24",
            "--platforms", "3",
            "--users", "2",
            "--collections", "2",
            "--play-sessions", "4",
            "--image-fidelity", "2",
            "--image-workers", "1",
            "--resources-path", str(resources),
            *flags,
        ],
    )  # fmt: skip
    assert generate_test_data.main() == 0
    return rows


def _without_images(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in row.items() if k not in IMAGE_FIELDS} for row in rows]


@pytest.mark.parametrize("flags", [("--image-limit", "5"), ("--no-images",)])
def test_image_flags_never_change_the_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flags: tuple[str, ...]
) -> None:
    every = _rom_rows(monkeypatch, tmp_path / "every")
    limited = _rom_rows(monkeypatch, tmp_path / "limited", *flags)

    assert len(every) == len(limited) == 24
    assert _without_images(every) == _without_images(limited)


@pytest.mark.parametrize("fidelity", ["1", "2"])
def test_a_dry_run_writes_no_image_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fidelity: str
) -> None:
    _rom_rows(monkeypatch, tmp_path, "--dry-run", "--image-fidelity", fidelity)

    assert not tmp_path.exists() or not any(tmp_path.rglob("*"))


def test_a_seed_rotates_the_gallery_and_feed_caches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rotated: list[str] = []

    _rom_rows(
        monkeypatch,
        tmp_path,
        rotate_cache=lambda: rotated.append("gallery"),
        rotate_feeds=lambda: rotated.append("feeds"),
    )

    assert rotated == ["gallery", "feeds"]


def test_the_utc_listener_is_removed_after_a_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    listeners: list[Callable[..., None]] = []
    pin_utc = generate_test_data._pin_utc

    def recorded(postgresql: bool) -> Callable[..., None]:
        listeners.append(pin_utc(postgresql))
        return listeners[-1]

    monkeypatch.setattr(generate_test_data, "_pin_utc", recorded)

    _rom_rows(monkeypatch, tmp_path)

    assert listeners
    assert not event.contains(sync_engine, "connect", listeners[0])


def test_a_cache_failure_still_reports_the_saved_seed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def unavailable() -> None:
        raise RedisError("connection refused")

    rows = _rom_rows(monkeypatch, tmp_path, rotate_cache=unavailable)

    captured = capsys.readouterr()
    assert "could not rotate the gallery cache" in captured.err
    assert "Done in" in captured.out
    assert len(rows) == 24


def _facts(seed: int) -> dict[str, Any]:
    return generate_test_data.make_facts(random.Random(seed), {})


def _without_metadata_extras(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in row.items() if k not in EXTRA_FIELDS} for row in rows]


def test_metadata_extras_never_shift_the_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seeded = _rom_rows(monkeypatch, tmp_path / "seeded")
    monkeypatch.setattr(generate_test_data, "extra_rng", lambda *_: random.Random(0))

    reseeded = _rom_rows(monkeypatch, tmp_path / "reseeded")

    assert _without_metadata_extras(seeded) == _without_metadata_extras(reseeded)


def test_rom_rows_carry_their_aliases_and_min_age(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    rows = _rom_rows(monkeypatch, tmp_path)

    aliased = next(r for r in rows if r["igdb_metadata"].get("alternative_names"))
    search_titles = aliased["search_titles"].split(SEARCH_TITLE_SEPARATOR)
    for alias in aliased["igdb_metadata"]["alternative_names"]:
        assert fold_search_title(alias) in search_titles
    assert any(row["min_age"] is not None for row in rows)


def test_ss_metadata_links_every_media_kind() -> None:
    metadata = generate_test_data.build_ss_metadata(random.Random(1), _facts(1))

    for kind in generate_test_data.SS_MEDIA_KINDS:
        assert metadata[f"{kind}_url"].startswith("https://")
        has_path = kind in generate_test_data.SS_PATH_KINDS
        assert (f"{kind}_path" in metadata) == has_path


def test_list_lengths_follow_the_measured_shape() -> None:
    rng = random.Random(7)
    least, p50, _, _, top = generate_test_data.LIST_SHAPES["igdb.keywords"]

    lengths = sorted(
        generate_test_data.sample_length(rng, "igdb.keywords") for _ in range(4000)
    )

    assert least <= lengths[0] and lengths[-1] <= top
    assert abs(lengths[len(lengths) // 2] - p50) <= 1


def test_the_longest_keyword_list_holds_distinct_keywords() -> None:
    top = generate_test_data.LIST_SHAPES["igdb.keywords"][-1]
    keywords = generate_test_data.KEYWORDS

    assert len(set(keywords)) == len(keywords) >= top


def test_a_wipe_clears_snapshots_before_the_saves_and_states_they_hold() -> None:
    class _Recorder:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        def execute(self, statement: Any) -> None:
            self.deleted.append(str(statement).removeprefix("DELETE FROM "))

    conn = _Recorder()

    generate_test_data._wipe(conn)  # type: ignore[arg-type]

    assert conn.deleted.index("snapshots") < conn.deleted.index("states")
    assert conn.deleted.index("snapshots") < conn.deleted.index("saves")


def test_igdb_metadata_always_has_ten_similar_games() -> None:
    metadata = generate_test_data.build_igdb_metadata(random.Random(3), _facts(3))

    assert len(metadata["similar_games"]) == 10
    for game in metadata["similar_games"]:
        assert game["slug"] == generate_test_data.slugify(game["name"])


def test_metadata_holds_every_key_a_scan_stores() -> None:
    igdb = generate_test_data.build_igdb_metadata(random.Random(4), _facts(4))
    ss = generate_test_data.build_ss_metadata(random.Random(4), _facts(4))

    assert IGDBMetadata.__required_keys__ <= igdb.keys()
    assert SSMetadata.__required_keys__ <= ss.keys()


def test_metadata_builders_draw_a_fixed_count_from_the_main_stream() -> None:
    rng = random.Random(11)
    for _ in range(20):
        facts = generate_test_data.make_facts(rng, {})
        generate_test_data.build_igdb_metadata(rng, facts)
        generate_test_data.build_ss_metadata(rng, facts)

    # A new draw on `rng` shifts every later row for a given --seed; draw from
    # `extra_rng` instead, or update this value if the shift is intended.
    assert rng.random() == 0.7712019761851616
