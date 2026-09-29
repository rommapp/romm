from unittest.mock import AsyncMock, MagicMock

import handler.install.auto_mode.runtime as runtime


class TestNotifyNeedsManual:
    """auto mode's own report() only calls this once per genuine transition
    into needs_manual (see AutoModeDriver._set), so this covers the payload
    it sends, not the de-duplication itself - that's the driver's job."""

    def _session(self, user_id=42, rom_id=7):
        return MagicMock(user_id=user_id, rom_id=rom_id)

    def _rom(self, name="Olden Era", fs_name="olden-era"):
        # MagicMock reserves the "name" kwarg for its own repr, not an
        # attribute - it has to be set afterwards.
        rom = MagicMock(fs_name=fs_name)
        rom.name = name
        return rom

    def test_notifies_the_session_owner(self, monkeypatch):
        from models.notification import NotificationKind, NotificationLevel

        session_handler = MagicMock()
        session_handler.get_session.return_value = self._session()
        monkeypatch.setattr(runtime, "db_install_session_handler", session_handler)
        monkeypatch.setattr(
            "handler.database.db_rom_handler.get_rom_visibility_label",
            lambda _id: self._rom(),
        )
        notify = AsyncMock()
        monkeypatch.setattr("handler.notification_handler.notify", notify)

        runtime._notify_needs_manual(1, "No known button on screen")

        notify.assert_awaited_once()
        args, _ = notify.await_args
        assert args[0] == 42
        assert args[1] == NotificationKind.INSTALL_NEEDS_MANUAL
        assert args[2] == NotificationLevel.WARNING
        assert args[3] == {
            "rom_id": 7,
            "rom_name": "Olden Era",
            "detail": "No known button on screen",
        }

    def test_missing_session_does_not_notify(self, monkeypatch):
        session_handler = MagicMock()
        session_handler.get_session.return_value = None
        monkeypatch.setattr(runtime, "db_install_session_handler", session_handler)
        notify = AsyncMock()
        monkeypatch.setattr("handler.notification_handler.notify", notify)

        runtime._notify_needs_manual(1, "No known button on screen")

        notify.assert_not_awaited()

    def test_a_notify_failure_does_not_raise(self, monkeypatch):
        session_handler = MagicMock()
        session_handler.get_session.return_value = self._session()
        monkeypatch.setattr(runtime, "db_install_session_handler", session_handler)
        monkeypatch.setattr(
            "handler.database.db_rom_handler.get_rom_visibility_label",
            lambda _id: None,
        )
        monkeypatch.setattr(
            "handler.notification_handler.notify",
            AsyncMock(side_effect=RuntimeError("redis is down")),
        )

        runtime._notify_needs_manual(1, "No known button on screen")  # must not raise


class TestReportNotifiesOnlyOnNeedsManual:
    def test_running_status_does_not_notify(self, monkeypatch):
        session_handler = MagicMock()
        monkeypatch.setattr(runtime, "db_install_session_handler", session_handler)
        notify_needs_manual = MagicMock()
        monkeypatch.setattr(
            runtime, "_notify_needs_manual", notify_needs_manual
        )

        driver = runtime.build_driver(1, ":50", MagicMock())
        driver.report("running", "click on 'Install'")

        notify_needs_manual.assert_not_called()

    def test_needs_manual_status_notifies(self, monkeypatch):
        session_handler = MagicMock()
        monkeypatch.setattr(runtime, "db_install_session_handler", session_handler)
        notify_needs_manual = MagicMock()
        monkeypatch.setattr(
            runtime, "_notify_needs_manual", notify_needs_manual
        )

        driver = runtime.build_driver(1, ":50", MagicMock())
        driver.report(runtime.STATUS_NEEDS_MANUAL, "No known button on screen")

        notify_needs_manual.assert_called_once_with(
            1, "No known button on screen"
        )
