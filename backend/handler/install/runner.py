"""Orchestrates a single server-side install run inside an RQ job.

Flow: mark the session INSTALLING, spin up a virtual display + VNC bridge,
launch the installer under bubblewrap via Proton/Wine, and wait on it while
the user drives it themselves through the VNC session. Two background
threads run alongside it: one just keeps the current dialog focused so it
actually renders and receives their input (see ``_focus_maintenance_loop``),
the other periodically snapshots whatever the installer has written so far
into a best-effort live manifest clients can already start pulling finished
pieces from (see ``_live_manifest_loop``). Once the installer exits, hash
everything it produced into the real, fully-verified manifest (STREAMING),
and finalize as DONE. Any failure marks the session FAILED and always tears
the sandbox down.

This module runs in the RQ worker process, not the web process.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from config import (
    INSTALL_DEFAULT_PROTON_BUILD,
    INSTALL_SANDBOX_ENABLED,
    INSTALL_TIMEOUT,
)
from handler.database import db_install_session_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.install.archive_prescan import (
    extract_and_rescan,
    is_archive_candidate,
    source_phase,
)
from handler.install.auto_mode.runtime import start_auto_mode
from handler.install.manifest import (
    LiveManifestEntry,
    delete_live_manifest,
    hash_files,
    manifest_total_bytes,
    read_live_manifest,
    scan_live_manifest,
    write_live_manifest,
    write_manifest,
)
from handler.install.progress import ThrottledProgress
from handler.install.proton_builds import (
    _download_proton_build,
    list_proton_builds,
    resolve_proton_path,
)
from handler.install.sandbox import SandboxSpec, build_bwrap_command
from handler.install.streaming_mode import stream_uncompleted_files_enabled
from handler.install.vnc import VncSession, start_vnc_session
from handler.install.windows_output import (
    collect_extra_work_dir_files,
    collect_windows_install_files,
    load_baseline,
    resolve_install_root,
    save_baseline,
    snapshot_windows_content_files,
)
from handler.redis_handler import install_queue
from logger.formatter import highlight as hl
from logger.logger import log
from models.install_session import InstallSessionState
from tasks.tasks import TaskType
from utils.install_cache import ensure_session_cache_dir

# noVNC static assets shipped in the sandbox image.
NOVNC_WEB_ROOT = "/usr/share/novnc"

# How often the focus-maintenance loop re-checks which window should have
# input focus - frequent enough that a newly appeared dialog (the user just
# clicked "Next") gets real focus, and therefore actually renders, within a
# fraction of a second of appearing.
FOCUS_MAINTENANCE_INTERVAL = 1.0

# How often the live-manifest loop rescans the installer's output - matches
# ThrottledProgress's cadence elsewhere in this module, frequent enough that
# a client sees a large file's sealed_bytes grow in near-real-time without
# rehashing so often it competes with the installer for disk I/O.
LIVE_MANIFEST_INTERVAL = 1.0


def enqueue_install(install_session_id: int) -> str:
    """Enqueue an install run on the dedicated install queue and return its job id."""
    job = install_queue.enqueue(
        run_install,
        install_session_id,
        job_timeout=INSTALL_TIMEOUT + 300,
        meta={"task_name": "Remote install", "task_type": TaskType.GENERIC},
    )
    return job.id


def _proton_prefix_dir(work_dir: Path) -> Path:
    """Per-session Proton/Wine prefix, isolated inside the session cache."""
    prefix = work_dir / "prefix"
    prefix.mkdir(parents=True, exist_ok=True)
    return prefix


def _uses_wine(installer_abs_path: str) -> bool:
    """Native .sh/.run installers run directly; everything else goes through
    Proton/Wine."""
    return not installer_abs_path.lower().endswith((".sh", ".run"))


def _ensure_proton_build(build_id: str) -> None:
    """Download and extract a Proton build synchronously if not yet installed.

    Called from within ``run_install`` — which itself runs as an RQ job on the
    install queue. Because the worker is single-threaded for that queue, we
    cannot enqueue a *second* RQ job (it would wait behind the current one
    forever). Instead, we call ``_download_proton_build`` directly: it streams
    the tarball, extracts it into ``PROTON_INSTALL_ROOT/<build_id>/``, and
    registers the build so subsequent scans see it instantly.
    """
    if resolve_proton_path(build_id) is not None:
        return
    _download_proton_build(build_id)


def _wine_or_proton(proton_build: str | None = None) -> str:
    """The Proton/Wine binary this install runs Windows installers under.

    ``proton_build`` is the session's chosen build id (see
    handler.install.proton_builds); an unset, unknown, or not-actually-
    installed id falls back to whichever build the manager discovers first
    (typically the first directory under PROTON_INSTALL_ROOT), or plain Wine
    if none are on disk. If no explicit build is requested, the global
    default from INSTALL_DEFAULT_PROTON_BUILD is consulted first and
    auto-downloaded on the worker's first use if missing (no pre-baking).
    """
    # Explicit session-level choice: use it if installed, else auto-download.
    if proton_build is not None:
        resolved = resolve_proton_path(proton_build)
        if resolved:
            return resolved
        try:
            _ensure_proton_build(proton_build)
            resolved = resolve_proton_path(proton_build)
            if resolved:
                return resolved
        except TimeoutError:
            log.warning(
                f"Auto-download of Proton {proton_build} timed out, falling back"
            )
        # proton_build was requested but never resolved (unknown id, or the
        # download failed/timed out) - fall through to the same defaults an
        # unset choice would use below, rather than dropping straight to
        # plain Wine (see this function's own docstring).

    # Global default from settings (library-management / stream-install config).
    if INSTALL_DEFAULT_PROTON_BUILD:
        path = resolve_proton_path(INSTALL_DEFAULT_PROTON_BUILD)
        if path:
            return path
        try:
            _ensure_proton_build(INSTALL_DEFAULT_PROTON_BUILD)
            path = resolve_proton_path(INSTALL_DEFAULT_PROTON_BUILD)
            if path:
                return path
        except TimeoutError:
            log.warning(
                f"Auto-download of default Proton '{INSTALL_DEFAULT_PROTON_BUILD}' "
                f"timed out, falling back"
            )

    # Fallback: first installed build discovered on disk.
    for build in list_proton_builds():
        if build.installed and build.path:
            return build.path
    return "wine"


def _is_proton(proton_or_wine: str) -> bool:
    """Distinguish Proton (its own `run <exe>` verb, STEAM_COMPAT_* env)
    from plain Wine (`wine <exe>` directly, WINEPREFIX) - Proton's own
    launcher script is always named exactly "proton"."""
    return Path(proton_or_wine).name == "proton"


def _windows_installer_path(
    installer_abs: Path, installer_search_root: Path, disc_source: Path | None
) -> str:
    """The installer's own path, translated to a drive Wine actually has
    (see _configure_drive_letters), instead of the bare Unix path Wine
    would otherwise only be able to resolve through z: - the entire reason
    z: gets removed there in the first place.
    """
    rel = installer_abs.relative_to(installer_search_root).as_posix().replace("/", "\\")
    root = "D:" if disc_source is not None else f"C:\\{_SOURCE_LINK_NAME}"
    return f"{root}\\{rel}"


def _build_inner_command(installer_abs_path: str, proton_or_wine: str) -> list[str]:
    """Command that Proton/Wine uses to run the installer.

    Proton's "run" and "waitforexitandrun" verbs both end up calling the
    exact same session.run(), but protonfixes.execute() - which applies
    Proton's own library of per-game/per-installer compatibility fixes -
    only actually does anything for "waitforexitandrun"; its own
    check_conditions() gates on that exact string, so "run" silently skips
    every fix (logged as "Skipping fix execution. We are probably running a
    unit test.", easy to miss). "waitforexitandrun" is also what real
    non-Steam launchers (umu-launcher, Faugus) use for exactly this reason.
    """
    if not _uses_wine(installer_abs_path):
        return ["/bin/sh", installer_abs_path]
    if _is_proton(proton_or_wine):
        return [proton_or_wine, "waitforexitandrun", installer_abs_path]
    return [proton_or_wine, installer_abs_path]


def _wine_drive_c_root(prefix_dir: Path, proton_or_wine: str) -> Path:
    """Where this run's "drive_c" actually ends up. Proton nests its real
    Wine prefix under a "pfx" subdirectory of STEAM_COMPAT_DATA_PATH; plain
    Wine uses WINEPREFIX (the session prefix dir) directly."""
    if _is_proton(proton_or_wine):
        return prefix_dir / "pfx"
    return prefix_dir


# A brand-new prefix's implicit bootstrap (registry hives, drive_c layout,
# fonts) on the very first "wine <installer>.exe" call is slow and, under
# this headless/sandboxed setup, occasionally races with launching the
# installer's own window in the same process and fails outright ("could not
# load kernel32.dll"). Booting the prefix as its own step first, before the
# installer or the focus-maintenance loop ever start, makes that failure
# attributable and avoids the race.
WINE_PREFIX_INIT_TIMEOUT = 60

# Even booted as its own step, this has been observed to fail intermittently
# ("could not load kernel32.dll") under CPU/IO contention on the host - a few
# retries clear it without a long fixed delay that would slow down the
# common, non-flaky case.
WINE_PREFIX_INIT_ATTEMPTS = 3
WINE_PREFIX_INIT_RETRY_DELAY = 3.0

# How much of a failed attempt's stderr to keep in the error message; wine's
# own diagnostic noise (ole/RPC warnings, winediag lines) is otherwise lost
# since the subprocess output is captured, not streamed to the job log.
_STDERR_TAIL_CHARS = 800


def _init_wine_prefix(
    proton_or_wine: str,
    *,
    installer_abs: str,
    work_dir: str,
    prefix_dir: str,
    display: str,
    extra_env: tuple[tuple[str, str], ...] = (),
) -> None:
    is_proton = _is_proton(proton_or_wine)
    label = "Proton" if is_proton else "Wine"
    wineboot = (
        [proton_or_wine, "run", "wineboot", "--init"]
        if is_proton
        else [proton_or_wine, "wineboot", "--init"]
    )
    argv = _wrap_for_sandbox(
        wineboot,
        installer_abs=installer_abs,
        work_dir=work_dir,
        proton_prefix=prefix_dir,
        display=display,
        proton_or_wine=proton_or_wine,
        extra_env=extra_env,
    )
    last_error: Exception | None = None
    for attempt in range(1, WINE_PREFIX_INIT_ATTEMPTS + 1):
        try:
            subprocess.run(
                argv,
                timeout=WINE_PREFIX_INIT_TIMEOUT,
                check=True,
                capture_output=True,
            )
            return
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or b"").decode(errors="replace")[-_STDERR_TAIL_CHARS:]
            last_error = RuntimeError(
                f"Failed to initialize the {label} prefix (exit {e.returncode}): {stderr}"
            )
        except subprocess.TimeoutExpired:
            last_error = RuntimeError(f"Timed out initializing the {label} prefix")

        if attempt < WINE_PREFIX_INIT_ATTEMPTS:
            log.warning(
                f"Wine prefix init attempt {attempt} failed, retrying: {last_error}"
            )
            time.sleep(WINE_PREFIX_INIT_RETRY_DELAY)

    assert last_error is not None
    raise last_error


# Where a plain (non-disc) install's source gets linked to inside drive_c,
# so it stays reachable purely via c: once z: is gone (see
# _configure_drive_letters and _windows_installer_path).
_SOURCE_LINK_NAME = ".romm-source"


def _configure_drive_letters(
    prefix_dir: Path,
    proton_or_wine: str,
    installer_search_root: Path,
    disc_source: Path | None,
) -> None:
    """Trim the fresh prefix down to what a real disc-based install would see.

    wineboot --init also maps z:\\ to the whole host filesystem - handy for
    desktop use, not for a sandboxed, untrusted installer: it hands it
    visibility (write access, wherever a bwrap bind happens to be writable)
    into everything bound in, and lets an installer that defaults its own
    destination to "next to its source" (some multi-part .bin/.iso releases
    do) land somewhere windows_output.py never scans - caught live,
    installing a real game, as a session marked DONE with nothing but a
    desktop shortcut in it.

    Safe to drop outright, rather than something Wine has to fall back to
    recreating on its own: _windows_installer_path never hands it a bare
    Unix path to translate in the first place, since the installer itself
    is always reachable through a drive this function sets up first - d:
    stands in for a real CD-ROM/DVD drive, pointed at the same read-only
    source bwrap already binds in for the installer to find its own sibling
    files, when ``disc_source`` is given (the ROM actually came from an
    archive/disc image). A plain single-file install has no real "disc" to
    speak of, so it gets linked into c:\\ instead, at _SOURCE_LINK_NAME,
    rather than an entirely unnecessary extra drive letter of its own.
    No a: at all: the only installers that would ever check for one don't
    exist in this library, and an extra drive is exactly the kind of thing
    this function exists to avoid handing out for free.
    """
    wineprefix = _wine_drive_c_root(prefix_dir, proton_or_wine)
    dosdevices = wineprefix / "dosdevices"
    (dosdevices / "z:").unlink(missing_ok=True)

    d_link = dosdevices / "d:"
    d_link.unlink(missing_ok=True)
    source_link = wineprefix / "drive_c" / _SOURCE_LINK_NAME
    source_link.unlink(missing_ok=True)
    if disc_source is not None:
        d_link.symlink_to(disc_source)
    else:
        source_link.symlink_to(installer_search_root)


def _mark_d_drive_as_cdrom(
    proton_or_wine: str,
    *,
    installer_abs: str,
    work_dir: str,
    prefix_dir: str,
    display: str,
    extra_env: tuple[tuple[str, str], ...] = (),
) -> None:
    """Tell Wine's own drive-type registry that d: is removable media.

    Only called when _configure_drive_letters actually added a d: (a real
    disc/archive source). Without this, an unconfigured extra drive is
    reported as a plain hard disk - indistinguishable, to an installer's
    own "pick a default install folder" logic, from a normal writable
    secondary drive. Caught live: an installer defaulted its destination to
    D:\\Games, which is read-only (d: stands in for the disc source) and
    the install failed outright - a real CD-ROM drive would have been
    skipped as a target instead, the same way c:\\ actually gets picked.

    Best-effort: a failure here still leaves d: present and readable, just
    not correctly typed, so it's logged and swallowed rather than failing
    the whole install over a registry tweak.
    """
    reg_cmd = (
        [proton_or_wine, "run", "reg"]
        if _is_proton(proton_or_wine)
        else [proton_or_wine, "reg"]
    )
    argv = _wrap_for_sandbox(
        [
            *reg_cmd,
            "add",
            r"HKEY_LOCAL_MACHINE\Software\Wine\Drives",
            "/v",
            "D:",
            "/d",
            "cdrom",
            "/f",
        ],
        installer_abs=installer_abs,
        work_dir=work_dir,
        proton_prefix=prefix_dir,
        display=display,
        proton_or_wine=proton_or_wine,
        extra_env=extra_env,
    )
    try:
        subprocess.run(
            argv, timeout=WINE_PREFIX_INIT_TIMEOUT, check=True, capture_output=True
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log.warning(f"Could not mark d: as a cdrom drive, leaving it untyped: {e}")


def run_install(install_session_id: int) -> None:
    """Entry point enqueued on the RQ worker for one install session.

    Wraps the actual run so the session's owner is notified exactly once,
    from the final DB state, regardless of which of `_run_install`'s many
    internal `_fail`/`_finalize_install` call sites got there.
    """
    try:
        _run_install(install_session_id)
    finally:
        _notify_install_end(install_session_id)


def _notify_install_end(install_session_id: int) -> None:
    session = db_install_session_handler.get_session(install_session_id)
    if session is None or session.state not in (
        InstallSessionState.DONE,
        InstallSessionState.FAILED,
    ):
        return

    try:
        import asyncio

        from handler.notification_handler import notify
        from models.notification import NotificationKind, NotificationLevel

        rom = db_rom_handler.get_rom_visibility_label(session.rom_id)
        rom_name = (rom.name or rom.fs_name) if rom else None
        failed = session.state == InstallSessionState.FAILED
        asyncio.run(
            notify(
                session.user_id,
                (
                    NotificationKind.INSTALL_FAILED
                    if failed
                    else NotificationKind.INSTALL_COMPLETED
                ),
                NotificationLevel.ERROR if failed else NotificationLevel.SUCCESS,
                {
                    "rom_id": session.rom_id,
                    "rom_name": rom_name,
                    "error": session.error,
                },
            )
        )
    except Exception:  # noqa: BLE001 - never let a notification failure mask the result
        log.error(
            f"Could not notify install session {install_session_id}'s end",
            exc_info=True,
        )


def _run_install(install_session_id: int) -> None:
    session = db_install_session_handler.get_session(install_session_id)
    if session is None:
        log.error(f"Install session {install_session_id} not found; aborting")
        return

    rom = db_rom_handler.get_rom(session.rom_id)
    if rom is None:
        # "Game", not "ROM": this message is user-facing (session.error), and
        # this path only ever runs for the Windows install flow.
        _fail(install_session_id, "Game no longer exists")
        return

    if not session.installer_path and not session.source_path:
        _fail(install_session_id, "No installer selected for this session")
        return

    # An archive/disc image holding the installer: either picked explicitly
    # (`source_path`, with `installer_path` naming the executable inside it) or
    # an archive selected as the installer itself (legacy sessions). Extracted
    # into a scratch dir, never the install cache, since it holds a copy of
    # the ROM's own contents rather than the install's output.
    source_rel = session.source_path
    inner_installer = session.installer_path
    if source_rel is None and inner_installer:
        try:
            probe = fs_rom_handler.resolve_installer_abs_path(rom, inner_installer)
        except (ValueError, FileNotFoundError) as e:
            _fail(install_session_id, str(e))
            return
        if is_archive_candidate(Path(probe)):
            source_rel, inner_installer = inner_installer, None

    extract_temp_dir: TemporaryDirectory[str] | None = None
    try:
        if source_rel is None:
            installer_abs = fs_rom_handler.resolve_installer_abs_path(
                rom, inner_installer or ""
            )
        else:
            source_abs = Path(
                fs_rom_handler.resolve_installer_abs_path(rom, source_rel)
            )
            db_install_session_handler.update_session(
                install_session_id,
                {
                    "phase": source_phase(source_abs).value,
                    "phase_detail": source_abs.name,
                },
            )
            result = extract_and_rescan(source_abs, inner_installer)
            if result is None:
                _fail(
                    install_session_id,
                    f"Nothing recognizable as an installer inside {source_abs.name}",
                )
                return
            extract_temp_dir, extract_root, chosen = result
            installer_abs = str(extract_root / chosen.path)
            db_install_session_handler.update_session(
                install_session_id,
                {
                    "source_path": source_rel,
                    "installer_path": chosen.path,
                    "phase": None,
                    "phase_detail": None,
                },
            )
    except (ValueError, FileNotFoundError) as e:
        _fail(install_session_id, str(e))
        return

    # InstallShield-based multi-part installers (their ISArcExtract/ISDone.dll
    # archive extractor) look for sibling data files (setup-N.bin, Data1.cab,
    # ...) next to the installer .exe at runtime, not just the .exe itself -
    # and older/DOS-era titles in particular sometimes nest those siblings a
    # subfolder or two below the installer rather than right next to it.
    # Without this, bwrap only exposes the single chosen file and the
    # installer fails with "It is not found any file specified for
    # ISArcExtract" the instant it needs a sibling it can't see. Bind the
    # installer's actual containing root read-only: the ROM's own library
    # directory normally, or the archive's scratch extraction root when the
    # installer came from inside an archive/ISO (see archive_prescan above).
    # A directory ro-bind is a real (recursive) mount, not a flat file
    # listing - every subfolder underneath is visible too, however deep.
    if extract_temp_dir is not None:
        installer_search_root = extract_root
    else:
        installer_search_root = fs_rom_handler.get_rom_root_abs_path(rom)
        if not installer_search_root.is_dir():
            installer_search_root = installer_search_root.parent

    # Only a source this session actually mounted/extracted gets a d: (see
    # _configure_drive_letters): a plain single-file install has no real
    # "disc" to represent, and handing it a d: anyway just gives its own
    # "default next to the source" logic an extra drive letter to land on
    # instead of c:. Deliberately not content-based (e.g. a ".bin" sitting
    # next to the installer): that extension means a real CD-ROM dump for a
    # console ROM, but a repack's own multi-part payload format for a PC
    # installer that reads it directly itself - the same suffix, two
    # unrelated things, and nothing here ever mounts the second kind.
    disc_source: Path | None = extract_root if extract_temp_dir is not None else None

    work_dir = ensure_session_cache_dir(install_session_id)
    prefix_dir = _proton_prefix_dir(work_dir)
    proton_or_wine = _wine_or_proton(session.proton_build)
    is_proton = _is_proton(proton_or_wine)

    extra_env: tuple[tuple[str, str], ...] = ()
    if is_proton:
        # Proton computes its own real Wine prefix from
        # STEAM_COMPAT_DATA_PATH (as "<that>/pfx", not WINEPREFIX directly)
        # and needs STEAM_COMPAT_CLIENT_INSTALL_PATH to exist, even though
        # nothing here is a real Steam install - a session-local, already-
        # bound-in directory satisfies it.
        steam_client_dir = work_dir / "steam-client"
        steam_client_dir.mkdir(parents=True, exist_ok=True)
        extra_env = (
            ("STEAM_COMPAT_DATA_PATH", str(prefix_dir)),
            ("STEAM_COMPAT_CLIENT_INSTALL_PATH", str(steam_client_dir)),
        )

    vnc: VncSession | None = None
    try:
        vnc = start_vnc_session(install_session_id, NOVNC_WEB_ROOT)
        db_install_session_handler.update_session(
            install_session_id,
            {
                "state": InstallSessionState.INSTALLING,
                "cache_path": str(work_dir),
                "vnc_url": vnc.public_url,
                "vnc_web_port": vnc.web_port,
            },
        )

        windows_baseline: frozenset[Path] = frozenset()
        installer_arg = installer_abs
        if _uses_wine(installer_abs):
            _init_wine_prefix(
                proton_or_wine,
                installer_abs=installer_abs,
                work_dir=str(work_dir),
                prefix_dir=str(prefix_dir),
                display=vnc.display,
                extra_env=extra_env,
            )
            _configure_drive_letters(
                prefix_dir, proton_or_wine, installer_search_root, disc_source
            )
            if disc_source is not None:
                _mark_d_drive_as_cdrom(
                    proton_or_wine,
                    installer_abs=installer_abs,
                    work_dir=str(work_dir),
                    prefix_dir=str(prefix_dir),
                    display=vnc.display,
                    extra_env=extra_env,
                )
            # Never the bare Unix path from here on: see
            # _windows_installer_path for why.
            installer_arg = _windows_installer_path(
                Path(installer_abs), installer_search_root, disc_source
            )
            # Wine's own bootstrap seeds Program Files with real stock stub
            # apps (wmplayer.exe, iexplore.exe, Common Files DLLs, ...) -
            # snapshot them now, before the installer ever runs, so they
            # don't get mistaken for what it wrote (see windows_output.py).
            saved_baseline = load_baseline(prefix_dir)
            if saved_baseline is None:
                windows_baseline = snapshot_windows_content_files(
                    _wine_drive_c_root(prefix_dir, proton_or_wine)
                )
                save_baseline(prefix_dir, windows_baseline)
            else:
                windows_baseline = saved_baseline

        # Some installers default their own destination to a top-level
        # "Games" folder regardless of which drives are actually available
        # - a targeted, single-path workaround for that one convention (see
        # SandboxSpec.games_fallback_dir). A subdirectory of work_dir, so
        # the usual discovery (collect_extra_work_dir_files) already covers
        # whatever lands here without any extra code.
        games_dir = work_dir / "Games"
        games_dir.mkdir(exist_ok=True)

        inner = _build_inner_command(installer_arg, proton_or_wine)
        argv = _wrap_for_sandbox(
            inner,
            installer_abs=installer_abs,
            work_dir=str(work_dir),
            proton_prefix=str(prefix_dir),
            display=vnc.display,
            proton_or_wine=proton_or_wine,
            extra_env=extra_env,
            installer_search_root=str(installer_search_root),
            games_fallback_dir=str(games_dir),
        )

        log.info(
            f"Launching installer for session {hl(str(install_session_id))} "
            f"via {hl('Proton' if is_proton else 'Wine')}"
        )

        # Only meaningful for the Windows/Wine path - collect_windows_install_files
        # is the same "Program Files" discovery already used at finalize time,
        # just run repeatedly instead of once after the fact. Native .sh/.run
        # installers have no such discovery target either way.
        stop_live_manifest = threading.Event()
        live_manifest_thread: threading.Thread | None = None
        if _uses_wine(installer_abs):
            live_manifest_thread = threading.Thread(
                target=_live_manifest_loop,
                args=(
                    work_dir,
                    _wine_drive_c_root(prefix_dir, proton_or_wine),
                    windows_baseline,
                    stop_live_manifest,
                ),
                daemon=True,
            )
            live_manifest_thread.start()
        timed_out = False
        try:
            _run_installer(
                argv,
                vnc.display,
                auto_mode_session=(install_session_id, work_dir),
            )
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            stop_live_manifest.set()
            if live_manifest_thread is not None:
                live_manifest_thread.join(timeout=2)

        if timed_out and not _install_output_looks_finished(work_dir):
            # Genuinely stuck (something was still mid-write, or nothing
            # was ever produced) - not safe to trust as a finished install.
            _fail(install_session_id, "Installer timed out")
            return
        if timed_out:
            log.warning(
                f"Install session {install_session_id} hit its timeout, but "
                "every discovered file looks finished and stable - most "
                "likely the installer reached its own final dialog (e.g. "
                '"Finish") and nobody was there to click it. Salvaging '
                "the install instead of discarding it."
            )

        # Installer exited (or timed out but looks done): it's done writing,
        # VNC is no longer needed. Set to None so the finally block below
        # doesn't try to stop it again.
        _enter_streaming(install_session_id, vnc)
        vnc = None
        _finalize_install(
            install_session_id,
            _wine_drive_c_root(prefix_dir, proton_or_wine),
            work_dir,
            windows_baseline,
        )
    except Exception as e:  # noqa: BLE001 - surface any runner failure to the UI
        log.error(f"Install session {install_session_id} failed: {e}")
        _fail(install_session_id, str(e))
    finally:
        if vnc is not None:
            vnc.stop()
        # Covers every exit path (done, failed, timed out) uniformly - a
        # successful run's own _finalize_install has already removed it by
        # the time we get here, so this is just a no-op then.
        delete_live_manifest(work_dir)
        if extract_temp_dir is not None:
            extract_temp_dir.cleanup()


def _files_under(files: list[Path], root: Path) -> list[Path]:
    """Filter to files actually under `root` - `Path.relative_to` raises for
    anything else, so a straggler discovered after `root` has been frozen
    (see resolve_install_root) is safer to just omit than to crash on."""
    kept = []
    for f in files:
        try:
            f.relative_to(root)
        except ValueError:
            continue
        kept.append(f)
    return kept


def _relocate_under(files: list[Path], root: Path, dest_root: Path) -> list[Path]:
    """Move each file from its real, `root`-relative location up to the same
    relative path under `dest_root`.

    The installer's actual output lives several levels deep inside the Wine
    prefix (``prefix/pfx/drive_c/...``), but every manifest path - and the
    download endpoint that serves it - is relative to the session's own
    cache directory (see ``handler.install.manifest``'s module docstring).
    Trimming the vendor folder off the *recorded* path (``resolve_install_root``)
    without also moving the *file* itself would leave the manifest pointing
    at a path that was never real on disk - exactly what it's for here.
    ``shutil.move`` is a same-filesystem rename in the common case (cheap,
    and safe even on a file the installer is still writing to - the process
    keeps its already-open handle on the same inode regardless of which
    directory entry points to it), falling back to copy+delete only if
    ``dest_root`` ever ends up on a different filesystem.
    """
    relocated = []
    for f in files:
        dest = dest_root / f.relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(dest))
        relocated.append(dest)
    return relocated


def _exclude_known_inodes(known: list[Path], candidates: list[Path]) -> list[Path]:
    """``candidates`` minus anything that's a hardlink (shares an inode) of
    something already in ``known``.

    Not a path comparison: c:\\'s own content can end up hardlinked into
    work_dir more than once, at *different* relative paths, if
    resolve_install_root resolves a different root on different calls (the
    live loop's own first scan vs. a later one, or _finalize_install's own
    fresh, complete scan) - its own docstring warns the result is meant to
    be resolved once and held fixed, but every caller here does its own. A
    hardlink of an already-known file shares its inode no matter which
    directory entry it sits behind, so that's what catches it instead.
    """
    known_inodes = set()
    for f in known:
        try:
            known_inodes.add(f.stat().st_ino)
        except OSError:
            pass
    result = []
    for f in candidates:
        try:
            if f.stat().st_ino in known_inodes:
                continue
        except OSError:
            continue
        result.append(f)
    return result


def _live_manifest_loop(
    work_dir: Path,
    prefix_dir: Path,
    windows_baseline: frozenset[Path],
    stop: threading.Event,
) -> None:
    """Periodically snapshot the installer's in-progress output so a client
    can start pulling finished pieces of a file before the whole install (and
    its real, fully-verified manifest) is done - see
    handler.install.manifest.scan_live_manifest for the sealing rule this
    relies on to never hand out a chunk that might still change.

    Every path this writes is relative to `work_dir` - the same directory
    the download endpoint resolves against (see handler.install.manifest's
    own module docstring) - never wherever Wine/Proton actually put the
    file (several levels deep inside the prefix). A newly-discovered file
    is hardlinked into `work_dir` (mirroring the resolved root's relative
    layout) the moment it's seen, not copied or moved: the installer keeps
    writing to the same inode no matter which directory entries point to
    it, so the file keeps growing live at both paths at once, and
    `_finalize_install`'s own separate, move-based relocation pass still
    finds the original completely undisturbed under `prefix_dir` once the
    installer exits - this loop never removes anything.
    """
    drive_c = prefix_dir / "drive_c"
    state: dict[str, LiveManifestEntry] = {}
    # Resolved once, the first scan that finds anything, then held fixed for
    # the rest of the run - recomputing it every scan risks it moving
    # mid-session and silently resetting every already-sealed file's
    # continuity key (see resolve_install_root's own docstring).
    root: Path | None = None
    while True:
        try:
            candidates = collect_windows_install_files(prefix_dir, windows_baseline)
            if root is None and candidates:
                root = resolve_install_root(drive_c, candidates)
            live_paths = []
            if root is not None:
                for f in _files_under(candidates, root):
                    dest = work_dir / f.relative_to(root)
                    if not dest.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        try:
                            os.link(f, dest)
                        except OSError:
                            continue  # transient (e.g. not sealed onto disk
                            # yet) - retry next scan
                    live_paths.append(dest)
            # z:\\ can't actually be removed (see _configure_drive_letters),
            # so an installer that writes "next to itself" - into work_dir,
            # the one thing z:\\ exposes that's actually recoverable, see
            # collect_extra_work_dir_files - remains possible in principle,
            # streamed the same as anything found through c:\\. Already
            # sitting in work_dir, so nothing to hardlink here, only to
            # fold in (deduped by inode, not path - see
            # _exclude_known_inodes) so it isn't sealed twice.
            live_paths += _exclude_known_inodes(
                live_paths, collect_extra_work_dir_files(work_dir)
            )
            if live_paths:
                # Checked fresh every scan (cheap, one Redis lookup) rather
                # than once at loop start, so toggling the setting mid-install
                # takes effect on the very next tick.
                state = scan_live_manifest(
                    work_dir,
                    live_paths,
                    state,
                    aggressive=stream_uncompleted_files_enabled(),
                )
                write_live_manifest(work_dir, state)
        except OSError as e:
            log.warning(f"Live manifest scan failed, will retry: {e}")
        if stop.wait(LIVE_MANIFEST_INTERVAL):
            return


def _enter_streaming(install_session_id: int, vnc: VncSession) -> None:
    """Move a session from INSTALLING to STREAMING and tear down its VNC.

    Called the moment the installer process exits (or a timed-out run looks
    finished): nothing left needs a display, and hashing a large install in
    _finalize_install can take a while, so there is no reason to keep
    Xvfb/x11vnc/icewm/picom/websockify running for the rest of that (see
    vnc.stop's own docstring for what it tears down).
    """
    db_install_session_handler.update_session(
        install_session_id,
        {
            "state": InstallSessionState.STREAMING,
            "vnc_url": None,
            "vnc_web_port": None,
            "auto_status": None,
            "auto_detail": None,
        },
    )
    vnc.stop()


def _finalize_install(
    install_session_id: int,
    prefix_dir: Path,
    work_dir: Path,
    windows_baseline: frozenset[Path] = frozenset(),
) -> None:
    """Hash whatever the installer produced and mark the session DONE.

    Raises if nothing was found, so the caller's except-block routes it to
    FAILED instead of finishing "successfully" with an empty manifest.
    """
    files = collect_windows_install_files(prefix_dir, windows_baseline)

    # One-time computation over the complete final file set - no flip-flop
    # risk the way the live loop's per-scan version would have, since this
    # only ever runs once (see resolve_install_root).
    root = resolve_install_root(prefix_dir / "drive_c", files)
    files = _files_under(files, root)
    # Move the discovered files out of the Wine prefix and up to `work_dir`
    # itself, mirroring the same (already vendor-folder-trimmed) relative
    # layout - see _relocate_under's own docstring for why this has to
    # happen, not just be recorded.
    files = _relocate_under(files, root, work_dir)

    # z:\\ can't actually be removed (Proton re-creates it on every real
    # launch regardless of what it's told to run - see
    # _configure_drive_letters), so an installer that resolves its own
    # location through it and writes "next to itself" - into work_dir, the
    # one thing z:\\ exposes that's actually recoverable, see
    # collect_extra_work_dir_files - remains possible in principle.
    files += _exclude_known_inodes(files, collect_extra_work_dir_files(work_dir))

    if not files:
        raise RuntimeError(
            "Installer finished but no files were found under drive_c or "
            "work_dir (it may have installed to a blacklisted or "
            "unrecognized path)"
        )

    report = ThrottledProgress(
        lambda hashed: db_install_session_handler.update_session(
            install_session_id, {"bytes_written": hashed}
        )
    )
    entries = hash_files(files, root=work_dir, on_progress=report)
    report.finish(manifest_total_bytes(entries))
    write_manifest(work_dir, entries)

    db_install_session_handler.update_session(
        install_session_id,
        {
            "state": InstallSessionState.DONE,
            "bytes_written": manifest_total_bytes(entries),
            "bytes_total": manifest_total_bytes(entries),
        },
    )


def _wrap_for_sandbox(
    inner: list[str],
    *,
    installer_abs: str,
    work_dir: str,
    proton_prefix: str,
    display: str,
    proton_or_wine: str,
    extra_env: tuple[tuple[str, str], ...] = (),
    installer_search_root: str | None = None,
    games_fallback_dir: str | None = None,
) -> list[str]:
    """Wrap the inner command in bubblewrap unless the sandbox is disabled."""
    if not INSTALL_SANDBOX_ENABLED:
        log.warning("Install sandbox is DISABLED; running installer unconfined")
        return inner
    # Bind in ONLY the build this session actually resolved to — not every
    # possible build directory. bwrap's --ro-bind fails outright if the source
    # path doesn't exist ("Can't find source path"), which was the root cause
    # of the crash when a stale env var pointed at a non-existent /opt/proton.
    # Guard with .exists() so a missing/stale path never takes down the run.
    # Plain Wine ("wine") lives under /usr already covered by the ro-bind, so
    # no extra bind is needed for it.
    ro_binds: tuple[str, ...] = ()
    if _is_proton(proton_or_wine):
        proton_path = Path(proton_or_wine)
        if proton_path.exists():
            ro_binds = (str(proton_path.resolve().parent),)
    # Multi-part installers need their sibling data files visible too, not
    # just the one .exe SandboxSpec always binds on its own - see run_install's
    # own comment on installer_search_root for why. Guarded the same way as
    # the Proton path above, for the same reason (never take down a run over
    # a path that turned out not to exist).
    if installer_search_root is not None and Path(installer_search_root).exists():
        ro_binds += (installer_search_root,)
    spec = SandboxSpec(
        installer_path=installer_abs,
        work_dir=work_dir,
        proton_prefix=proton_prefix,
        display=display,
        ro_binds=ro_binds,
        extra_env=extra_env,
        games_fallback_dir=games_fallback_dir,
    )
    return build_bwrap_command(spec, inner)


def _run_installer(
    argv: list[str],
    display: str,
    auto_mode_session: tuple[int, Path] | None = None,
) -> None:
    """Run the installer argv with a hard timeout, keeping it usable meanwhile.

    The user drives the installer themselves through the VNC session - this
    just waits on the process, while a background thread keeps whatever
    dialog is currently showing actually focused (see
    ``_focus_maintenance_loop`` for why that's needed at all). With
    ``auto_mode_session`` (session id, work dir) a second thread runs the
    experimental auto mode, which only acts while the session's ``auto_mode``
    flag is on (see handler.install.auto_mode).
    """
    proc = subprocess.Popen(argv)
    stop_focus_loop = threading.Event()
    focus_thread = threading.Thread(
        target=_focus_maintenance_loop, args=(display, stop_focus_loop), daemon=True
    )
    focus_thread.start()
    auto_thread: threading.Thread | None = None
    if auto_mode_session is not None:
        auto_thread = start_auto_mode(
            auto_mode_session[0], display, auto_mode_session[1], stop_focus_loop
        )
    try:
        proc.wait(timeout=INSTALL_TIMEOUT)
        # The only signal available after the fact for "did the installer
        # actually finish, or just give up/crash very early" - caught live,
        # an install exiting with nothing to show for it a few seconds
        # after Install was clicked, with nothing else in the log to say
        # why. A non-zero code at least narrows that down next time.
        if proc.returncode != 0:
            log.warning(
                f"Installer process exited with code {proc.returncode} "
                "(not necessarily a failure - some installers use this for "
                "e.g. 'reboot needed')"
            )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    finally:
        stop_focus_loop.set()
        focus_thread.join(timeout=2)
        if auto_thread is not None:
            auto_thread.join(timeout=2)


def _install_output_looks_finished(work_dir: Path) -> bool:
    """Best-effort check for "the installer most likely already reached its
    own end, and was just sitting on a final dialog (a 'Finish' button, an
    auto-launched game, ...) nobody clicked/closed" - used only as a
    fallback once the hard INSTALL_TIMEOUT has already fired (see
    run_install), to decide whether to salvage whatever is on disk as a
    finished install instead of unconditionally discarding it.

    Caught live: an install (see the runner.py log entry for the full
    story) whose actual file output - all 436 files, including the
    uninstaller InnoSetup writes as its literal last step - finished within
    two minutes, but the sandbox process itself sat idle for the rest of
    the hour-long timeout because nobody was watching to click the
    installer's own final "Finish" button. The old behavior discarded a
    fully complete, correctly-written install as a plain failure.

    True only if the live manifest already being tracked (see
    _live_manifest_loop) has at least one entry, and every one of them is
    fully sealed - its size hasn't changed since the loop's last scan,
    `LIVE_MANIFEST_INTERVAL` seconds before the timeout fired. A genuinely
    still-in-progress (or truly stuck) install almost always has something
    mid-write at that exact instant; one that's actually finished has
    nothing left to grow into. This is a much weaker signal in isolation
    than it is here: it only ever gets consulted after the full, real
    `INSTALL_TIMEOUT` has already elapsed with the process never exiting on
    its own, which is most of what makes it trustworthy.
    """
    live = read_live_manifest(work_dir)
    if not live:
        return False
    return all(e.sealed_bytes >= e.size_bytes for e in live.values())


@dataclass
class _FocusState:
    """Carried across every tick of one install run's focus-maintenance loop.

    ``seen_ids`` is every non-chrome window id ever observed this run, so a
    freshly-appeared window can be told apart from one that's been on screen
    for a while. ``target`` is the window this loop is currently deliberately
    keeping focused - kept sticky across ticks (see _focus_installer_window)
    rather than recomputed by size every time, so grabbing focus onto a new,
    small dialog doesn't get silently undone a second later by a bigger,
    already-seen window still sitting behind it.
    """

    seen_ids: set[str] = field(default_factory=set)
    target: str | None = None


def _focus_maintenance_loop(display: str, stop: threading.Event) -> None:
    """Keep whatever installer dialog is currently on screen actually usable.

    This never clicks or types anything on the user's behalf - the user
    drives the installer themselves through the VNC session (see
    InstallVncOverlay), the same way they'd click through any other
    installer. What it does do: without real X11 input focus, a freshly
    mapped Wine/Proton window has been observed not just to ignore
    keystrokes, but to never paint its own content at all (an empty/black
    client area indistinguishable from "not rendered"). IceWM's own
    focus-on-map policy doesn't reliably cover a session's very first
    window (see docker/icewm-preferences), and every later dialog in the
    same wizard needs the exact same treatment as it replaces the last one.
    Runs unsandboxed (it never touches the installer's files, only the
    shared X display) since xdotool talks to the X server directly
    regardless of which mount/pid namespace the installer's client process
    is in. A fresh ``_FocusState`` is scoped to this one call (one thread per
    install run - see ``_run_installer``), so it never leaks across sessions.
    """
    env = {**os.environ, "DISPLAY": display}
    state = _FocusState()
    _focus_installer_window(env, state)
    while not stop.wait(FOCUS_MAINTENANCE_INTERVAL):
        _focus_installer_window(env, state)


# IceWM's own window furniture on a session used for nothing but a single
# installer - excluded so _focus_installer_window never grabs focus onto the
# WM itself (or one of its per-window decoration wrappers) instead of the
# actual dialog. "Frame"/"Container"/"TitleBar"/"SysMenu"/"Lower"/"Close" are
# IceWM's own reparenting sub-windows, generic to *every* managed window
# (including the real one) - without excluding them too, their geometry can
# tie or beat the actual client's and win the largest-area pick instead.
# Exact names observed on IceWM 3.3.1's default theme; harmless if a future
# theme adds more (worst case, that extra window becomes a focus candidate).
_ICEWM_CHROME_NAMES = frozenset(
    {
        "IceTopWin",
        "IceBottom",
        "IceEdge",
        "IceRootProxy",
        "YXTrayProxy",
        "Default IME",
        "Input",
        "Frame",
        "Container",
        "TitleBar",
        "SysMenu",
        "Lower",
        "Close",
    }
)


def _focus_installer_window(env: dict, state: _FocusState) -> None:
    """Force real X11 input focus onto the installer's own window.

    IceWM's automatic focus-on-map policy (FocusOnMapTransient, see
    docker/icewm-preferences) is meant to cover this, but has been observed
    not to reliably transfer focus to a fresh session's very first dialog -
    unfocused, a Wine/Proton window has been observed not just to ignore the
    real user's keystrokes but to never paint its own content at all. Belt
    and suspenders: explicitly (re-)grab focus on whatever looks like the
    actual app window on every check, rather than trusting the WM got it
    right once at map time.

    Picking "largest window" alone was found to pick the *wrong* window for
    some multi-window installer stages (older InstallShield-style wizards
    especially): a small dialog that needs immediate keyboard input (e.g.
    "press Up to dismiss") pops up while a bigger, already-on-screen window
    (a splash/progress dialog) stays put behind it - by area alone the
    bigger one always wins, so real focus never reaches the dialog the user
    is actually trying to interact with, every single tick. Preferring
    whichever window is *new* since the last check (via `state.seen_ids`)
    catches exactly that case; once chosen, that window stays the sticky
    `state.target` across later ticks (still re-asserted each time, per the
    docstring above) instead of being immediately re-evaluated by size again
    - otherwise the bigger window would just steal focus straight back a
    second later, undoing the fix. Falls back to the largest-area heuristic
    only when there's no "new" window to prefer (nothing changed) or the
    current target itself has disappeared.
    """
    try:
        result = subprocess.run(
            ["xdotool", "search", "--onlyvisible", "--name", "."],
            env=env,
            check=False,
            capture_output=True,
            timeout=5,
            text=True,
        )
    except OSError, subprocess.TimeoutExpired:
        return

    candidates: list[tuple[str, int]] = []
    for window_id in result.stdout.split():
        try:
            name = subprocess.run(
                ["xdotool", "getwindowname", window_id],
                env=env,
                check=False,
                capture_output=True,
                timeout=2,
                text=True,
            ).stdout.strip()
            if not name or name in _ICEWM_CHROME_NAMES or name.startswith("IceWM "):
                continue
            geometry = subprocess.run(
                ["xdotool", "getwindowgeometry", "--shell", window_id],
                env=env,
                check=False,
                capture_output=True,
                timeout=2,
                text=True,
            ).stdout
            dims = dict(
                line.split("=", 1) for line in geometry.splitlines() if "=" in line
            )
            area = int(dims.get("WIDTH", 0)) * int(dims.get("HEIGHT", 0))
        except OSError, subprocess.TimeoutExpired, ValueError:
            continue
        candidates.append((window_id, area))

    if not candidates:
        return

    candidate_ids = {window_id for window_id, _ in candidates}
    new_ids = candidate_ids - state.seen_ids
    state.seen_ids |= candidate_ids

    if new_ids:
        # Several could appear in the same one-second tick - the numerically
        # largest id is the most recently created one, X11 ids being handed
        # out in increasing order within a session.
        try:
            state.target = max(new_ids, key=int)
        except ValueError:
            state.target = next(iter(new_ids))
    elif state.target not in candidate_ids:
        # The sticky target disappeared (closed/replaced) with nothing
        # freshly new to pick up in its place - fall back to whatever's
        # biggest rather than focusing nothing at all.
        state.target = max(candidates, key=lambda c: c[1])[0]
    # else: target is unchanged and still on screen - keep reasserting focus
    # on it below, exactly as before.

    subprocess.run(
        ["xdotool", "windowfocus", "--sync", state.target],
        env=env,
        check=False,
        capture_output=True,
        timeout=2,
    )


def _fail(install_session_id: int, error: str) -> None:
    db_install_session_handler.update_session(
        install_session_id,
        {
            "state": InstallSessionState.FAILED,
            "error": error,
            "vnc_url": None,
            "vnc_web_port": None,
            "phase": None,
            "phase_detail": None,
        },
    )
