import sys
from collections.abc import Callable
from datetime import datetime, tzinfo
from pathlib import Path
from typing import Any

import pytest
from redis.exceptions import RedisError
from tools import generate_test_data

from handler.database import db_rom_handler
from models.rom import Rom

IMAGE_FIELDS = {"path_cover_s", "path_cover_l", "path_screenshots"}


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "_FrozenDatetime":
        return cls(2026, 1, 1, 12, 0, tzinfo=tz)


def _rom_rows(
    monkeypatch: pytest.MonkeyPatch,
    resources: Path,
    *flags: str,
    rotate_cache: Callable[[], None] = lambda: None,
) -> list[dict[str, Any]]:
    """Run the seeder, recording rom rows instead of inserting anything."""
    rows: list[dict[str, Any]] = []

    def record(conn: object, model: type, batch: list[dict[str, Any]]) -> None:
        if model is Rom:
            rows.extend(batch)

    monkeypatch.setattr(generate_test_data, "bulk_insert", record)
    monkeypatch.setattr(generate_test_data, "_advance_sequences", lambda *_: None)
    monkeypatch.setattr(generate_test_data, "datetime", _FrozenDatetime)
    monkeypatch.setattr(db_rom_handler, "invalidate_filter_values_cache", rotate_cache)
    # main() registers a connect listener on the shared engine; keep it out of other tests.
    monkeypatch.setattr("sqlalchemy.event.listens_for", lambda *_, **__: lambda f: f)
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


def test_media_is_refused_at_mosaic_fidelity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["generate_test_data.py", "--image-media"])

    with pytest.raises(SystemExit):
        generate_test_data.main()
    assert "--image-media needs --image-fidelity 2 or 3" in capsys.readouterr().err


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
