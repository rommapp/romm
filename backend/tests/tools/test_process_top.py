import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import psutil
import pytest
from tools.process_top import (
    LINGER_SECONDS,
    Row,
    TreeView,
    format_csv,
    format_jsonl,
    format_table,
    main,
    take_sample,
)


def _proc(
    pid: int, cpu_seconds: float, pss: int | None = 150 * 1024 * 1024
) -> MagicMock:
    proc = MagicMock(pid=pid)
    proc.memory_info.return_value = SimpleNamespace(rss=200 * 1024 * 1024)
    proc.cpu_times.return_value = SimpleNamespace(user=cpu_seconds, system=0.0)
    proc.num_threads.return_value = 4
    proc.num_fds.return_value = 12
    proc.info = {"ppid": 1}
    if pss is None:
        proc.memory_full_info.side_effect = psutil.AccessDenied(pid)
    else:
        proc.memory_full_info.return_value = SimpleNamespace(pss=pss, uss=pss // 2)
    return proc


def _row(role: str, rss: float, pss: float | None) -> Row:
    return Row(
        "2026-11-21T14:02:05-06:00", role, "main", 1, rss, pss, None, None, 4, None
    )


def test_cpu_percent_comes_from_the_change_since_the_last_sample(mocker) -> None:
    processes = mocker.patch("tools.process_top.romm_processes")
    cpu_seen: dict[int, float] = {}

    processes.return_value = [(_proc(10, cpu_seconds=1.0), "api")]
    (first,) = take_sample(cpu_seen, elapsed=0)
    processes.return_value = [(_proc(10, cpu_seconds=1.5), "api")]
    (second,) = take_sample(cpu_seen, elapsed=1.0)

    assert first.cpu_percent is None
    assert second.cpu_percent == 50.0
    assert (second.rss_mb, second.pss_mb, second.uss_mb) == (200.0, 150.0, 75.0)


def test_a_process_without_readable_pss_still_reports_its_rss(mocker) -> None:
    mocker.patch(
        "tools.process_top.romm_processes",
        return_value=[(_proc(10, 1.0, pss=None), "valkey")],
    )

    (row,) = take_sample({}, elapsed=0)

    assert (row.rss_mb, row.pss_mb, row.uss_mb) == (200.0, None, None)


def test_a_process_that_exits_mid_read_is_skipped(mocker) -> None:
    gone = _proc(10, 1.0)
    gone.memory_info.side_effect = psutil.NoSuchProcess(10)
    mocker.patch("tools.process_top.romm_processes", return_value=[(gone, "api")])

    assert take_sample({}, elapsed=0) == []


def test_table_totals_pss_when_every_process_has_it() -> None:
    lines = list(
        format_table([_row("api", 200.0, 150.0), _row("rq_cron", 60.0, 50.0)], True)
    )

    assert lines[0].split()[:4] == ["time", "role", "kind", "pid"]
    assert lines[1].startswith("14:02:05 api")
    assert lines[-1].split() == ["total", "pss", "200.0"]


def test_table_falls_back_to_rss_when_a_process_lacks_pss() -> None:
    lines = list(
        format_table([_row("api", 200.0, 150.0), _row("valkey", 10.0, None)], True)
    )

    assert lines[-1].split() == ["total", "rss", "210.0"]


def test_only_the_first_sample_carries_a_header() -> None:
    rows = [_row("api", 200.0, 150.0)]

    assert list(format_csv(rows, header=True))[0].startswith("time,role,kind,pid")
    assert not list(format_csv(rows, header=False))[0].startswith("time,")
    assert list(format_table(rows, header=False))[0] == ""


def test_jsonl_writes_one_object_per_process() -> None:
    (line,) = format_jsonl([_row("api", 200.0, 150.0)], header=True)

    assert json.loads(line)["role"] == "api"
    assert json.loads(line)["pss_mb"] == 150.0


def test_no_romm_processes_explains_where_to_run_it(mocker, capsys) -> None:
    mocker.patch("tools.process_top.romm_processes", return_value=[])

    assert main(["--count", "1"]) == 1

    assert "no RomM processes found" in capsys.readouterr().err


def test_unreadable_pss_is_explained_once(mocker, capsys) -> None:
    mocker.patch(
        "tools.process_top.romm_processes",
        return_value=[(_proc(10, 1.0, pss=None), "api")],
    )

    assert main(["--count", "2", "--interval", "0.01"]) == 0

    err = capsys.readouterr().err
    assert err.count("no permission to read the PSS of pid 10") == 1


def test_a_bad_interval_is_refused(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--interval", "0"])

    assert "--interval must be more than 0" in capsys.readouterr().err


def _node(role: str, kind: str, pid: int, ppid: int | None, pss: float | None) -> Row:
    return Row(
        "2026-11-21T14:02:05-06:00",
        role,
        kind,
        pid,
        100.0,
        pss,
        10.0,
        None,
        4,
        None,
        ppid,
    )


def _parent_line(lines: list[str]) -> str:
    return next(
        line for line in lines if "rq_scan_worker" in line and "+--" not in line
    )


def _scan_frame(horse_pss: float | None = 130.0) -> list[Row]:
    return [
        _node("rq_scan_worker", "parent", 10, 1, 80.0),
        _node("rq_scan_worker", "scheduler", 11, 10, 78.0),
        _node("rq_scan_worker", "work_horse", 12, 10, horse_pss),
        _node("rq_cron", "main", 20, 1, 107.0),
    ]


def test_tree_shows_a_parent_with_its_children_and_their_total() -> None:
    lines = list(TreeView().render(_scan_frame(), now=0.0))

    parent = _parent_line(lines)
    horse = next(line for line in lines if "work_horse" in line)
    assert "288" in parent
    assert "`-- rq_scan_worker work_horse" in horse
    assert horse.split()[3] == "12"


def test_a_total_with_an_unreadable_child_is_marked_incomplete() -> None:
    lines = list(TreeView().render(_scan_frame(horse_pss=None), now=0.0))

    parent = _parent_line(lines)
    assert "158+" in parent


def test_tree_remembers_a_process_that_just_exited() -> None:
    view = TreeView()
    list(view.render(_scan_frame(), now=0.0))

    lines = list(view.render(_scan_frame()[:2] + _scan_frame()[3:], now=5.0))

    gone = next(line for line in lines if "seen 5 s" in line)
    assert "work_horse" in gone and "12" in gone and "peak 130 MB" in gone


def test_tree_keeps_the_highest_pss_it_saw() -> None:
    view = TreeView()
    list(view.render(_scan_frame(horse_pss=150.0), now=0.0))
    list(view.render(_scan_frame(horse_pss=90.0), now=2.0))

    lines = list(view.render(_scan_frame()[:2], now=4.0))

    assert any("peak 150 MB" in line for line in lines)


def test_tree_forgets_an_exited_process_after_a_while() -> None:
    view = TreeView()
    list(view.render(_scan_frame(), now=0.0))
    list(view.render(_scan_frame()[:2], now=1.0))

    lines = list(view.render(_scan_frame()[:2], now=1.0 + LINGER_SECONDS + 1))

    assert not any("gone in the last" in line for line in lines)
