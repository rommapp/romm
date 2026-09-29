"""Direct copy path for ROMs that don't need an installer.

Non-Windows platforms have nothing to run, so `start_install_session` moves
them straight to STREAMING and enqueues this instead of `run_install`: copy
the ROM's own files into the session cache, hash them, and finish.

This module runs in the RQ worker process, not the web process.
"""

from __future__ import annotations

from pathlib import Path

from config import INSTALL_TIMEOUT
from handler.database import db_install_session_handler, db_rom_handler
from handler.filesystem import fs_rom_handler
from handler.install.copier import copy_files
from handler.install.manifest import (
    build_manifest,
    manifest_total_bytes,
    write_manifest,
)
from handler.install.progress import ThrottledProgress
from handler.redis_handler import install_queue
from logger.formatter import highlight as hl
from logger.logger import log
from models.install_session import InstallSessionState
from models.rom import Rom
from tasks.tasks import TaskType
from utils.install_cache import ensure_session_cache_dir


def enqueue_stream_copy(install_session_id: int) -> str:
    """Enqueue a stream-copy run on the dedicated install queue."""
    job = install_queue.enqueue(
        run_stream_copy,
        install_session_id,
        job_timeout=INSTALL_TIMEOUT + 300,
        meta={"task_name": "Remote install (copy)", "task_type": TaskType.GENERIC},
    )
    return job.id


def _rom_copy_pairs(
    rom: Rom, rom_root: Path, work_dir: Path
) -> list[tuple[Path, Path]]:
    """(src, dst) pairs for every file the ROM is made of."""
    if rom_root.is_dir():
        return [
            (rom_root / f.path, work_dir / f.path)
            for f in fs_rom_handler.list_rom_files_flat(rom)
        ]
    return [(rom_root, work_dir / rom.fs_name)]


def run_stream_copy(install_session_id: int) -> None:
    """Entry point enqueued on the RQ worker for one stream-copy session."""
    session = db_install_session_handler.get_session(install_session_id)
    if session is None:
        log.error(f"Install session {install_session_id} not found; aborting")
        return

    rom = db_rom_handler.get_rom(session.rom_id)
    if rom is None:
        _fail(install_session_id, "ROM no longer exists")
        return

    try:
        rom_root = fs_rom_handler.get_rom_root_abs_path(rom)
        work_dir = ensure_session_cache_dir(install_session_id)
        pairs = _rom_copy_pairs(rom, rom_root, work_dir)
        bytes_total = sum(f.size_bytes for f in fs_rom_handler.list_rom_files_flat(rom))

        db_install_session_handler.update_session(
            install_session_id,
            {"cache_path": str(work_dir), "bytes_total": bytes_total},
        )

        log.info(
            f"Copying {hl(str(len(pairs)))} file(s) for install session "
            f"{hl(str(install_session_id))}"
        )
        report = ThrottledProgress(
            lambda written: db_install_session_handler.update_session(
                install_session_id, {"bytes_written": written}
            )
        )
        copied = copy_files(pairs, on_progress=report)
        report.finish(copied)

        entries = build_manifest(work_dir)
        write_manifest(work_dir, entries)

        db_install_session_handler.update_session(
            install_session_id,
            {
                "state": InstallSessionState.DONE,
                "bytes_written": manifest_total_bytes(entries),
                "bytes_total": manifest_total_bytes(entries),
            },
        )
    except Exception as e:  # noqa: BLE001 - surface any copy failure to the UI
        log.error(f"Stream-copy session {install_session_id} failed: {e}")
        _fail(install_session_id, str(e))


def _fail(install_session_id: int, error: str) -> None:
    db_install_session_handler.update_session(
        install_session_id,
        {"state": InstallSessionState.FAILED, "error": error},
    )
