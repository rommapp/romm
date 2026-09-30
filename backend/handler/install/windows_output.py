r"""Best-effort discovery of where a Windows installer put the game.

Wine/Proton maps `C:\` to `<prefix>/drive_c`. Scanning the whole drive is the
only way to catch installers that default to a custom path (e.g.
`C:\Games\...`) instead of Program Files, but a fresh prefix's own
bootstrap (wineboot --init) seeds real, non-empty stock files across it
(Program Files' stub apps like wmplayer.exe/iexplore.exe, a synthesized
`users\\<name>` profile tree, ...) - not "a couple of empty vendor folders"
as one might assume. Left unfiltered, a prefix where the installer never
wrote anything (crashed, or was never really run) still "finds" these and
gets marked DONE with no game in it.

Three layers handle that:
- `BLACKLIST_PATTERNS`: relative-to-`drive_c` path patterns that are always
  Windows/Wine/Proton noise and never worth scanning at all, wherever they
  appear (not just at the top level).
- A before/after diff: `snapshot_windows_content_files` is called right
  after `_init_wine_prefix` (before the installer ever runs) to capture
  Wine's own baseline everywhere else, and `collect_windows_install_files`
  excludes it - this is what actually filters the Program Files stubs and
  the synthesized user-profile tree, since neither matches a blacklist
  pattern.
- `resolve_install_root`: once the installer's own output is known, decides
  whether the exposed/stored path should start at `drive_c` or one level
  further in, inside a known vendor folder (e.g. `GOG Games`) - the vendor
  folder's own name isn't part of the game's identity.

`collect_extra_work_dir_files` is a separate, best-effort fallback for the
same underlying problem one level up: z:\\ (Wine's own fallback mapping for
the whole sandboxed filesystem, see runner._configure_drive_letters) can't
actually be removed - Proton re-creates it on every real launch regardless
of what's passed as the installer's own argument - so an installer that
still resolves its own location through it, and decides to write "next to
itself", remains possible in principle. Only work_dir is worth checking for
that, not the rest of z:\\: it's a real bind mount, the same directory
whether read from inside the sandbox or, like this whole module, from the
outer worker process afterward. Nothing else z:\\ exposes is - the
sandboxed installer's own /tmp is a fresh tmpfs private to bwrap's mount
namespace, gone the moment its process exits, well before this ever runs;
the rest is read-only binds nothing can write to in the first place.
Treated as part of the same disk as c:\\ (no separate root in the exposed
manifest): merged into the same file list, relocated the same way.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

# Relative-to-drive_c path patterns that are always Wine/Windows/Proton
# system noise, regardless of what any installer does - never worth walking
# at all. Segments are matched case-insensitively; "*" matches exactly one
# path segment (e.g. each Wine user profile name).
BLACKLIST_PATTERNS: tuple[tuple[str, ...], ...] = (
    ("windows",),
    ("programdata",),
    ("proton_shortcuts",),
    ("users", "*", "appdata", "local", "temp"),
)

# Top-level drive_c folders known to be an installer's own generic target
# directory rather than part of the game's identity - trimmed from the
# front of an exposed path (see resolve_install_root) so e.g.
# `GOG Games/Freedom Planet/...` becomes `Freedom Planet/...`.
KNOWN_VENDOR_DIR_NAMES = ("Program Files", "Program Files (x86)", "GOG Games")


def _is_blacklisted(rel_parts: tuple[str, ...]) -> bool:
    lower = tuple(part.lower() for part in rel_parts)
    return any(
        len(lower) >= len(pattern)
        and all(seg == "*" or seg == lower[i] for i, seg in enumerate(pattern))
        for pattern in BLACKLIST_PATTERNS
    )


def _iter_content_files(prefix_dir: Path):
    drive_c = prefix_dir / "drive_c"
    if not drive_c.is_dir():
        return
    for p in drive_c.rglob("*"):
        if not p.is_file():
            continue
        if _is_blacklisted(p.relative_to(drive_c).parts):
            continue
        yield p


def snapshot_windows_content_files(prefix_dir: Path) -> frozenset[Path]:
    """Baseline of what's already under drive_c before the installer runs -
    Wine's own bootstrap content, to be excluded later."""
    return frozenset(_iter_content_files(prefix_dir))


_BASELINE_FILE = ".romm-baseline.json"


def save_baseline(prefix_root: Path, baseline: frozenset[Path]) -> None:
    """Persist the stock-content baseline next to the Wine prefix, so a later
    install into the same cache (a patch, a reinstall) keeps excluding only
    Wine's own files and not the game installed earlier."""
    (prefix_root / _BASELINE_FILE).write_text(
        json.dumps(sorted(str(p) for p in baseline))
    )


def load_baseline(prefix_root: Path) -> frozenset[Path] | None:
    try:
        raw = json.loads((prefix_root / _BASELINE_FILE).read_text())
    except OSError, ValueError:
        return None
    return frozenset(Path(p) for p in raw)


def collect_windows_install_files(
    prefix_dir: Path, baseline: frozenset[Path] = frozenset()
) -> list[Path]:
    """Files under drive_c (outside the blacklisted system directories) that
    weren't already there in ``baseline`` (see snapshot_windows_content_files)."""
    return [p for p in _iter_content_files(prefix_dir) if p not in baseline]


def resolve_install_root(drive_c: Path, files: Iterable[Path]) -> Path:
    """Where manifest paths should be computed relative to.

    If every discovered file lives under the same known vendor folder
    directly under drive_c (e.g. `GOG Games`), root there so exposed paths
    start at the game's own folder instead of the installer's generic
    target directory. Falls back to drive_c itself when that's ambiguous
    (files span multiple top-level folders) or the shared folder isn't a
    recognized vendor name.

    Callers must resolve this once per session (the first scan that sees
    any files) and hold the result fixed for the rest of the run - the live
    manifest keys its chunk-sealing continuity by path, so a root that
    changes mid-session would silently reset every already-sealed file's
    state.
    """
    top_segments: set[str] = set()
    for f in files:
        try:
            top_segments.add(f.relative_to(drive_c).parts[0])
        except ValueError, IndexError:
            return drive_c
    if len(top_segments) == 1:
        (only,) = top_segments
        if only in KNOWN_VENDOR_DIR_NAMES:
            return drive_c / only
    return drive_c


# Entries directly under work_dir that are never installed game content:
# the Wine prefix (drive_c already covered separately by
# collect_windows_install_files - the rest of it is Wine/Proton's own
# bookkeeping: system.reg, dosdevices, ...), Proton's own stub client dir,
# and this session's own manifest files.
_SESSION_OWNED_TOP_LEVEL_NAMES = frozenset(
    (
        "prefix",
        "steam-client",
        ".romm-install-manifest.json",
        ".romm-install-manifest.live.json",
    )
)


def collect_extra_work_dir_files(work_dir: Path) -> list[Path]:
    """Files an installer wrote directly into its own session's writable
    area (work_dir) instead of through c:\\/d:\\ - see this module's own
    docstring for why work_dir specifically, and nothing else z:\\ exposes.
    """
    try:
        entries = list(work_dir.iterdir())
    except OSError:
        return []
    found: list[Path] = []
    for entry in entries:
        if entry.name in _SESSION_OWNED_TOP_LEVEL_NAMES:
            continue
        if entry.is_file():
            found.append(entry)
        elif entry.is_dir():
            found.extend(p for p in entry.rglob("*") if p.is_file())
    return found
