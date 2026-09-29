"""Glue between the auto mode driver and one install session."""

from __future__ import annotations

import threading
from pathlib import Path

from config.config_manager import config_manager as cm
from handler.database import db_install_session_handler
from handler.install.manifest import read_live_manifest
from logger.logger import log

from .catalog import load_catalog
from .driver import STATUS_NEEDS_MANUAL, AutoModeDriver, make_x11_actor, make_x11_observer


def _extra_buttons() -> list[dict]:
    try:
        return list(cm.get_config().INSTALL_AUTO_MODE_EXTRA_BUTTONS)
    except Exception as e:  # noqa: BLE001 - a broken config must not stop the built-in list
        log.debug(f"Could not read auto mode extra buttons: {e}")
        return []


def _notify_needs_manual(install_session_id: int, detail: str | None) -> None:
    """Tell the session's owner auto mode is stuck and needs a hand.

    Runs on the driver's own background thread, not the RQ job's, so this
    has no running event loop to hook into - same `asyncio.run` pattern as
    `runner._notify_install_end`.
    """
    try:
        import asyncio

        from handler.database import db_rom_handler
        from handler.notification_handler import notify
        from models.notification import NotificationKind, NotificationLevel

        session = db_install_session_handler.get_session(install_session_id)
        if session is None:
            return
        rom = db_rom_handler.get_rom_visibility_label(session.rom_id)
        rom_name = (rom.name or rom.fs_name) if rom else None
        asyncio.run(
            notify(
                session.user_id,
                NotificationKind.INSTALL_NEEDS_MANUAL,
                NotificationLevel.WARNING,
                {"rom_id": session.rom_id, "rom_name": rom_name, "detail": detail},
            )
        )
    except Exception:  # noqa: BLE001 - never let a notification failure stop auto mode
        log.error(
            f"Could not notify install session {install_session_id} needs manual help",
            exc_info=True,
        )


def build_driver(
    install_session_id: int, display: str, work_dir: Path
) -> AutoModeDriver:
    def enabled() -> bool:
        session = db_install_session_handler.get_session(install_session_id)
        return bool(session and session.auto_mode)

    def progress() -> int:
        live = read_live_manifest(work_dir)
        return sum(e.size_bytes for e in live.values()) if live else 0

    def report(status: str | None, detail: str | None) -> None:
        db_install_session_handler.update_session(
            install_session_id, {"auto_status": status, "auto_detail": detail}
        )
        # `_set` on the driver's own side only calls `report` on a genuine
        # change, so this fires exactly once per transition into the state,
        # not on every tick spent stuck there.
        if status == STATUS_NEEDS_MANUAL:
            _notify_needs_manual(install_session_id, detail)

    catalog = load_catalog(_extra_buttons())
    return AutoModeDriver(
        catalog=catalog,
        observe=make_x11_observer(display, catalog),
        act=make_x11_actor(display),
        enabled=enabled,
        progress=progress,
        report=report,
    )


def start_auto_mode(
    install_session_id: int, display: str, work_dir: Path, stop: threading.Event
) -> threading.Thread:
    driver = build_driver(install_session_id, display, work_dir)
    thread = threading.Thread(target=driver.run, args=(stop,), daemon=True)
    thread.start()
    return thread
