#!/usr/bin/env python3
"""Print the memory and CPU of every RomM process, once every few seconds.

`--format tree --interval 2` redraws the process tree instead, with each parent's
memory including its children and a short memory of processes that just exited.
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

try:
    import psutil
except ImportError:
    sys.exit(
        "process_top: psutil is not installed. Run this with RomM's own Python, "
        "which has it: inside the container, `python` already is."
    )

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.process_stats import process_kinds, romm_processes  # noqa: E402

MIB: Final = 1024 * 1024
FORMATS: Final = ("table", "csv", "jsonl", "tree")
CLEAR_SCREEN: Final = "\x1b[H\x1b[2J"
LINGER_SECONDS: Final = 30
# Kinds that are the role itself rather than a child of it.
_ROLE_KINDS: Final = frozenset({"main", "master", "parent"})


@dataclass(frozen=True)
class Row:
    time: str
    role: str
    kind: str
    pid: int
    rss_mb: float
    pss_mb: float | None
    uss_mb: float | None
    cpu_percent: float | None
    threads: int
    fds: int | None
    ppid: int | None = None


PSS_NOT_LINUX: Final = (
    "pss_mb and uss_mb need Linux, so this system shows only rss_mb, which counts "
    "shared memory once in every process. Run it in the RomM container for PSS."
)
PSS_DENIED: Final = (
    "no permission to read the PSS of pid {pid} ({role}). Try "
    "`sudo .venv/bin/python backend/tools/process_top.py`. "
    "See docs/OPENTELEMETRY.md, 'When PSS is denied'."
)
NO_PROCESSES: Final = (
    "no RomM processes found among the {seen} processes this tool can see. It only "
    "sees its own machine or container, so run it inside the RomM container: "
    "`docker exec <container> python /backend/tools/process_top.py` "
    "(in the dev container, /app/backend/tools/process_top.py). It looks for "
    "gunicorn or main.py, rq worker, rq cron, watchfiles, nginx and valkey-server."
)


def _note(problems: set[str] | None, message: str) -> None:
    if problems is not None:
        problems.add(message)


def _mb(value: int) -> float:
    return round(value / MIB, 1)


def warn(message: str) -> None:
    print(f"process_top: {message}", file=sys.stderr)


def take_sample(
    cpu_seen: dict[int, float], elapsed: float, problems: set[str] | None = None
) -> list[Row]:
    """Read every RomM process once, updating cpu_seen for the next call's CPU %.

    Args:
        problems: If given, collects one explanation per reading that failed.
    """
    now = datetime.now(UTC).astimezone().isoformat(timespec="seconds")
    rows, seen = [], {}
    processes = list(romm_processes())
    kinds = process_kinds(processes)
    for proc, role in processes:
        try:
            with proc.oneshot():
                rss = proc.memory_info().rss
                cpu = proc.cpu_times()
                threads = proc.num_threads()
                pss: float | None
                uss: float | None
                try:
                    full = proc.memory_full_info()
                    pss, uss = _mb(full.pss), _mb(full.uss)
                except AttributeError:
                    pss = uss = None
                    _note(problems, PSS_NOT_LINUX)
                except psutil.AccessDenied:
                    pss = uss = None
                    _note(problems, PSS_DENIED.format(pid=proc.pid, role=role))
                try:
                    fds: int | None = proc.num_fds()
                except psutil.AccessDenied, AttributeError:
                    fds = None
        except psutil.Error:
            continue
        cpu_seconds = cpu.user + cpu.system
        previous = cpu_seen.get(proc.pid)
        cpu_percent = (
            round((cpu_seconds - previous) / elapsed * 100, 1)
            if previous is not None and elapsed > 0
            else None
        )
        seen[proc.pid] = cpu_seconds
        rows.append(
            Row(
                now,
                role,
                kinds[proc.pid],
                proc.pid,
                _mb(rss),
                pss,
                uss,
                cpu_percent,
                threads,
                fds,
                proc.info["ppid"],
            )
        )
    cpu_seen.clear()
    cpu_seen.update(seen)
    return sorted(rows, key=lambda row: (row.role, row.pid))


def _cell(value: object) -> str:
    return "-" if value is None else str(value)


def format_table(rows: list[Row], header: bool) -> Iterator[str]:
    columns = "{:<8} {:<20} {:<10} {:>7} {:>8} {:>8} {:>8} {:>6} {:>7} {:>5}"
    if not header:
        yield ""
    if header:
        yield columns.format(
            "time",
            "role",
            "kind",
            "pid",
            "rss_mb",
            "pss_mb",
            "uss_mb",
            "cpu%",
            "threads",
            "fds",
        )
    for row in rows:
        yield columns.format(
            row.time[11:19],
            row.role,
            row.kind,
            row.pid,
            row.rss_mb,
            _cell(row.pss_mb),
            _cell(row.uss_mb),
            _cell(row.cpu_percent),
            row.threads,
            _cell(row.fds),
        )
    if rows:
        # PSS adds up to the real total; RSS counts shared pages in every process.
        known = [row.pss_mb for row in rows if row.pss_mb is not None]
        label = "total pss" if len(known) == len(rows) else "total rss"
        total = sum(known) if label == "total pss" else sum(r.rss_mb for r in rows)
        yield f"{'':<8} {label:<20} {'':<10} {'':>7} {'':>8} {round(total, 1):>8}"


def _tree_cell(value: float | None, width: int = 7) -> str:
    return f"{'?':>{width}}" if value is None else f"{value:>{width}.0f}"


class TreeView:
    """Draws each sample as a process tree and remembers what it has seen.

    A process that vanishes stays listed for LINGER_SECONDS with its last size and
    its highest PSS, so a work horse that lives for a few seconds leaves a trace.
    """

    def __init__(self) -> None:
        self._first_seen: dict[int, float] = {}
        self._peak: dict[int, float] = {}
        self._last: dict[int, tuple[str, float | None]] = {}
        self._gone: dict[int, tuple[str, float, float | None, float, float]] = {}

    @staticmethod
    def _label(row: Row) -> str:
        return row.role if row.kind in _ROLE_KINDS else f"{row.role} {row.kind}"

    def render(self, rows: list[Row], now: float) -> Iterator[str]:
        by_pid = {row.pid: row for row in rows}
        children: dict[int | None, list[Row]] = {}
        for row in rows:
            parent = row.ppid if row.ppid in by_pid else None
            children.setdefault(parent, []).append(row)
            self._first_seen.setdefault(row.pid, now)
            self._peak[row.pid] = max(self._peak.get(row.pid, 0.0), row.pss_mb or 0.0)
            self._last[row.pid] = (self._label(row), row.pss_mb)
        for pid in [pid for pid in self._last if pid not in by_pid]:
            label, pss = self._last.pop(pid)
            self._gone[pid] = (
                label,
                now - self._first_seen.pop(pid),
                pss,
                self._peak.pop(pid),
                now,
            )
        self._gone = {
            pid: gone
            for pid, gone in self._gone.items()
            if now - gone[4] <= LINGER_SECONDS
        }

        def total(row: Row) -> tuple[float, bool]:
            own, unknown = row.pss_mb or 0.0, row.pss_mb is None
            for child in children.get(row.pid, []):
                child_total, child_unknown = total(child)
                own, unknown = own + child_total, unknown or child_unknown
            return own, unknown

        yield (
            f"{'':<40}{'pid':>7}{'own':>7}{'with kids':>10}{'uss':>7}{'peak':>7}"
            "   PSS in MB"
        )

        def draw(row: Row, prefix: str, last: bool, root: bool) -> Iterator[str]:
            kids = sorted(children.get(row.pid, []), key=lambda r: (r.role, r.pid))
            branch = "" if root else prefix + ("`-- " if last else "+-- ")
            with_kids = ""
            if kids:
                amount, unknown = total(row)
                with_kids = f"{amount:.0f}{'+' if unknown else ''}"
            yield (
                f"{branch + self._label(row):<40}{row.pid:>7}{_tree_cell(row.pss_mb)}"
                f"{with_kids:>10}{_tree_cell(row.uss_mb)}{self._peak[row.pid]:>7.0f}"
            )
            deeper = prefix if root else prefix + ("    " if last else "|   ")
            for index, kid in enumerate(kids):
                yield from draw(kid, deeper, index == len(kids) - 1, False)

        roots = sorted(children.get(None, []), key=lambda r: (r.role, r.pid))
        for root in roots:
            yield from draw(root, "", True, True)
        if self._gone:
            yield ""
            yield f"gone in the last {LINGER_SECONDS} s:"
            for pid, (label, lived, pss, peak, died) in sorted(
                self._gone.items(), key=lambda item: item[1][4]
            ):
                yield (
                    f"  {label:<36}{pid:>7}  seen {lived:.0f} s, last "
                    f"{_tree_cell(pss, 0).strip()} MB, peak {peak:.0f} MB, "
                    f"{now - died:.0f} s ago"
                )


def format_csv(rows: list[Row], header: bool) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(Row.__dataclass_fields__))
    if header:
        writer.writeheader()
    writer.writerows(asdict(row) for row in rows)
    yield from buffer.getvalue().splitlines()


def format_jsonl(rows: list[Row], header: bool) -> Iterator[str]:
    yield from (json.dumps(asdict(row)) for row in rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--interval", type=float, default=5.0, help="Seconds between samples."
    )
    parser.add_argument(
        "--count", type=int, default=0, help="Samples to take. 0 runs until stopped."
    )
    parser.add_argument("--format", choices=FORMATS, default="table")
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval must be more than 0 seconds")
    if args.count < 0:
        parser.error("--count must be 0 or more")
    view = TreeView()

    def format_tree(rows: list[Row], header: bool) -> Iterator[str]:
        return view.render(rows, time.monotonic())

    formatters = {
        "table": format_table,
        "csv": format_csv,
        "jsonl": format_jsonl,
        "tree": format_tree,
    }
    formatter = formatters[args.format]
    redraw = args.format == "tree" and args.count != 1

    cpu_seen: dict[int, float] = {}
    reported: set[str] = set()
    found_any = False
    last = time.monotonic()
    taken = 0
    try:
        while args.count == 0 or taken < args.count:
            now = time.monotonic()
            problems: set[str] = set()
            rows = take_sample(cpu_seen, now - last, problems)
            last = now
            found_any = found_any or bool(rows)
            if not rows:
                problems.add(NO_PROCESSES.format(seen=len(psutil.pids())))
            # Each explanation once, not once per sample.
            for problem in sorted(problems - reported):
                warn(problem)
            reported |= problems
            if redraw:
                sys.stdout.write(CLEAR_SCREEN)
            for line in formatter(rows, header=taken == 0):
                print(line)
            # Flushed each time, so a file it's redirected to fills as it goes.
            sys.stdout.flush()
            taken += 1
            if args.count == 0 or taken < args.count:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    except BrokenPipeError:
        # The reader closed early, as `| head` does. Point stdout at devnull so
        # Python's exit flush doesn't raise again.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    return 0 if found_any else 1


if __name__ == "__main__":
    sys.exit(main())
