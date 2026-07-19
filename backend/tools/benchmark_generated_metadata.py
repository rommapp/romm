#!/usr/bin/env python3
"""Benchmark the roms_metadata read path before/after migration 0098.

Migration 0098 replaces the derive-on-read ``roms_metadata`` VIEW (which
JSON-parses provider blobs per row, per query) with STORED generated columns
plus indexes. This script measures the difference on whatever library is
currently in the configured database.

By default it runs the full before/after comparison against the SAME data:
it times the query set at ``head`` (generated columns), downgrades to 0097
(the old derive-on-read view), times again, then upgrades back to ``head``.
Downgrade/upgrade only swap the view definition and add/drop columns, so the
row data is identical across both measurements.

Run from the backend directory against a throwaway/dev database:

    uv run tools/benchmark_generated_metadata.py                 # before/after
    uv run tools/benchmark_generated_metadata.py --once          # current state only
    uv run tools/benchmark_generated_metadata.py --explain       # also print plans

Seed a realistic library first, e.g.:

    uv run tools/generate_test_data.py --roms 100000 --no-images --wipe
"""

from __future__ import annotations

import argparse
import os
import statistics
import subprocess  # nosec B404 - drives local alembic, no external input
import sys
import time

# Allow running as `python3 tools/benchmark_generated_metadata.py` from backend/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text  # noqa: E402

from handler.database.base_handler import sync_engine  # noqa: E402

_PREV_REVISION = "0097_roms_platform_fs_size_index"
_HEAD_REVISION = "0098_generated_metadata_columns"

# Representative slices of the gallery/search workload in get_roms. Each sorts
# or filters on a derived column, which the old view had to compute for every
# row before it could sort or filter. A deep OFFSET makes the whole-table cost
# unavoidable (LIMIT alone could stop early on an indexed column).
_QUERIES: dict[str, str] = {
    "sort_by_rating": (
        "SELECT r.id FROM roms r JOIN roms_metadata m ON m.rom_id = r.id "
        "ORDER BY m.average_rating DESC, r.id LIMIT 72 OFFSET :offset"
    ),
    "sort_by_release_date": (
        "SELECT r.id FROM roms r JOIN roms_metadata m ON m.rom_id = r.id "
        "ORDER BY m.first_release_date DESC, r.id LIMIT 72 OFFSET :offset"
    ),
    "filter_player_count": (
        "SELECT COUNT(*) FROM roms r JOIN roms_metadata m ON m.rom_id = r.id "
        "WHERE m.player_count <> '1'"
    ),
}


def _run_alembic(*sub_args: str) -> None:
    print(f"  alembic {' '.join(sub_args)} ...", flush=True)
    subprocess.run(  # nosec B603 B607 - fixed args, local dev tool
        ["uv", "run", "alembic", *sub_args],
        check=True,
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    )


def _time_query(sql: str, params: dict, repeats: int) -> list[float]:
    """Return per-run wall-clock milliseconds (one warm-up run discarded)."""
    stmt = text(sql)
    with sync_engine.connect() as conn:
        conn.execute(stmt, params).fetchall()  # warm caches/plan
        samples = []
        for _ in range(repeats):
            start = time.perf_counter()
            conn.execute(stmt, params).fetchall()
            samples.append((time.perf_counter() - start) * 1000)
    return samples


def _measure(offset: int, repeats: int) -> dict[str, float]:
    results = {}
    for name, sql in _QUERIES.items():
        params = {"offset": offset} if ":offset" in sql else {}
        samples = _time_query(sql, params, repeats)
        results[name] = min(samples)  # best-of-N: least noise from other load
        print(
            f"    {name:<22} "
            f"min={min(samples):8.1f}ms  median={statistics.median(samples):8.1f}ms"
        )
    return results


def _explain(offset: int) -> None:
    print("\n=== Query plans (EXPLAIN ANALYZE) ===")
    with sync_engine.connect() as conn:
        for name, sql in _QUERIES.items():
            params = {"offset": offset} if ":offset" in sql else {}
            print(f"\n--- {name} ---")
            for row in conn.execute(text(f"EXPLAIN ANALYZE {sql}"), params):
                print("  " + "  ".join(str(c) for c in row))


def _rom_count() -> int:
    with sync_engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM roms")).scalar_one()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Measure only the current DB state (no downgrade/upgrade flip)",
    )
    parser.add_argument(
        "--repeats", type=int, default=5, help="Timed runs per query (default: 5)"
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=5000,
        help="OFFSET for the deep-page sorts (default: 5000)",
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Also print EXPLAIN ANALYZE plans for the current revision",
    )
    args = parser.parse_args()

    total = _rom_count()
    if total == 0:
        sys.exit("No roms in the database. Seed one first (see the module docstring).")
    print(f"Library size: {total:,} roms\n")

    if args.once:
        print("Current revision:")
        _measure(args.offset, args.repeats)
        if args.explain:
            _explain(args.offset)
        return

    print("[after] head (generated columns + indexes):")
    after = _measure(args.offset, args.repeats)
    if args.explain:
        _explain(args.offset)

    print("\n[before] downgrading to the derive-on-read view:")
    _run_alembic("downgrade", _PREV_REVISION)
    try:
        before = _measure(args.offset, args.repeats)
    finally:
        print("\nRestoring head:")
        _run_alembic("upgrade", "head")

    print("\n=== Before/after (best-of-N wall clock) ===")
    print(f"{'query':<22}{'before (0097)':>16}{'after (0098)':>16}{'speedup':>10}")
    for name in _QUERIES:
        b, a = before[name], after[name]
        speedup = f"{b / a:6.1f}x" if a > 0 else "n/a"
        print(f"{name:<22}{b:>14.1f}ms{a:>14.1f}ms{speedup:>10}")


if __name__ == "__main__":
    main()
