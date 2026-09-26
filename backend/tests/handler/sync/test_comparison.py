"""Tests for sync comparison algorithm."""

from dataclasses import dataclass
from datetime import datetime, timezone

from handler.sync.comparison import (
    SyncComparisonResult,
    compare_missing_server_save,
    compare_save_state,
    roms_to_check_for_removals,
)


class TestCompareIdenticalHashes:
    def test_identical_hashes_returns_no_op(self):
        result = compare_save_state(
            client_hash="abc123",
            client_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            server_hash="abc123",
            server_updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            device_last_synced_at=None,
        )
        assert result.action == "no_op"
        assert "identical" in result.reason.lower()

    def test_identical_hashes_with_sync_history(self):
        result = compare_save_state(
            client_hash="abc123",
            client_updated_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            server_hash="abc123",
            server_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            device_last_synced_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert result.action == "no_op"


class TestCompareWithSyncHistory:
    """Tests where device has synced before (device_last_synced_at is set)."""

    def test_client_changed_returns_upload(self):
        result = compare_save_state(
            client_hash="new_hash",
            client_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            server_hash="old_hash",
            server_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            device_last_synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
        assert result.action == "upload"

    def test_server_changed_returns_download(self):
        result = compare_save_state(
            client_hash="old_hash",
            client_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            server_hash="new_hash",
            server_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            device_last_synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
        assert result.action == "download"

    def test_both_changed_returns_conflict(self):
        result = compare_save_state(
            client_hash="client_new",
            client_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            server_hash="server_new",
            server_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            device_last_synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
        assert result.action == "conflict"

    def test_neither_changed_returns_no_op(self):
        result = compare_save_state(
            client_hash="different_hash",
            client_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            server_hash="other_hash",
            server_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            device_last_synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )
        assert result.action == "no_op"


class TestCompareWithoutSyncHistory:
    """Tests where device has never synced (device_last_synced_at is None)."""

    def test_client_newer_returns_upload(self):
        result = compare_save_state(
            client_hash="client_hash",
            client_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            server_hash="server_hash",
            server_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            device_last_synced_at=None,
        )
        assert result.action == "upload"

    def test_server_newer_returns_download(self):
        result = compare_save_state(
            client_hash="client_hash",
            client_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            server_hash="server_hash",
            server_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            device_last_synced_at=None,
        )
        assert result.action == "download"

    def test_same_timestamp_different_hashes_returns_conflict(self):
        ts = datetime(2026, 1, 5, tzinfo=timezone.utc)
        result = compare_save_state(
            client_hash="hash_a",
            client_updated_at=ts,
            server_hash="hash_b",
            server_updated_at=ts,
            device_last_synced_at=None,
        )
        assert result.action == "conflict"

    def test_same_timestamp_same_hashes_returns_no_op(self):
        ts = datetime(2026, 1, 5, tzinfo=timezone.utc)
        result = compare_save_state(
            client_hash="same",
            client_updated_at=ts,
            server_hash="same",
            server_updated_at=ts,
            device_last_synced_at=None,
        )
        assert result.action == "no_op"

    def test_same_timestamp_none_hashes_returns_no_op(self):
        ts = datetime(2026, 1, 5, tzinfo=timezone.utc)
        result = compare_save_state(
            client_hash=None,
            client_updated_at=ts,
            server_hash=None,
            server_updated_at=ts,
            device_last_synced_at=None,
        )
        assert result.action == "no_op"


class TestCompareReturnType:
    def test_returns_named_tuple(self):
        result = compare_save_state(
            client_hash="a",
            client_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            server_hash="a",
            server_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            device_last_synced_at=None,
        )
        assert isinstance(result, SyncComparisonResult)
        assert isinstance(result.action, str)
        assert isinstance(result.reason, str)


class TestCompareRemovedVersions:
    REMOVED = datetime(2026, 1, 2, tzinfo=timezone.utc)
    BEFORE = datetime(2026, 1, 1, tzinfo=timezone.utc)
    AFTER = datetime(2026, 1, 3, tzinfo=timezone.utc)

    def _compare(self, client_hash, client_updated_at, **overrides):
        kwargs = {
            "client_hash": client_hash,
            "client_updated_at": client_updated_at,
            "server_hash": "current",
            "server_updated_at": self.BEFORE,
            "device_last_synced_at": self.BEFORE,
            "removed_at": {"removed": self.REMOVED, "current": self.REMOVED},
        }
        return compare_save_state(**{**kwargs, **overrides})

    def test_a_version_written_before_its_removal_downloads(self):
        # Its timestamp is newer than the server's current save, which alone
        # would answer upload.
        assert self._compare("removed", self.REMOVED).action == "download"

    def test_the_same_bytes_written_after_the_removal_are_progress(self):
        assert self._compare("removed", self.AFTER).action == "upload"

    def test_the_current_version_stays_in_sync_even_if_once_removed(self):
        assert self._compare("current", self.BEFORE).action == "no_op"

    def test_a_client_that_reports_no_digest_compares_by_time(self):
        result = self._compare(None, self.AFTER, device_last_synced_at=None)
        assert result.action == "upload"


class TestCompareMissingServerSave:
    REMOVED = datetime(2026, 1, 2, tzinfo=timezone.utc)
    LOST = {"def456": REMOVED, "abc123": REMOVED}

    def test_a_version_written_before_the_slot_lost_it_is_deleted(self):
        result = compare_missing_server_save(
            "abc123", datetime(2026, 1, 1, tzinfo=timezone.utc), self.LOST
        )
        assert result.action == "delete"

    def test_the_same_bytes_written_after_the_loss_are_uploaded(self):
        result = compare_missing_server_save(
            "abc123", datetime(2026, 1, 3, tzinfo=timezone.utc), self.LOST
        )
        assert result.action == "upload"

    def test_bytes_nobody_deleted_are_uploaded(self):
        # Offering it back costs a deletion that misses that device; deleting
        # it would cost the save.
        assert (
            compare_missing_server_save("fresh", self.REMOVED, self.LOST).action
            == "upload"
        )

    def test_a_client_that_reports_no_digest_is_uploaded(self):
        assert (
            compare_missing_server_save(None, self.REMOVED, self.LOST).action
            == "upload"
        )

    def test_a_slot_that_lost_nothing_is_uploaded(self):
        assert (
            compare_missing_server_save("abc123", self.REMOVED, {}).action == "upload"
        )


@dataclass(frozen=True)
class _Save:
    rom_id: int
    slot: str | None
    content_hash: str | None


class TestRomsToCheckForRemovals:
    def test_only_saves_that_differ_from_their_slot_are_checked(self):
        current: dict[tuple[int, str | None], _Save] = {
            (1, "autosave"): _Save(1, "autosave", "same"),
            (2, "autosave"): _Save(2, "autosave", "current"),
        }
        client_saves = [
            _Save(1, "autosave", "same"),
            _Save(2, "autosave", "older"),
            _Save(3, "autosave", "unknown"),
            _Save(4, None, "archival"),
        ]

        assert roms_to_check_for_removals(client_saves, current) == {2, 3}
