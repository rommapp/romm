"""Tests for sync comparison algorithm."""

from datetime import datetime, timezone

from handler.sync.comparison import SyncComparisonResult, compare_save_state


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

    def test_identical_hashes_win_over_a_stale_baseline(self):
        result = compare_save_state(
            client_hash="same",
            client_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            server_hash="same",
            server_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            device_last_synced_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
            device_last_sync_hash="stale",
            device_last_sync_server_hash="stale",
        )
        assert result.action == "no_op"
        assert result.reason == "Content is identical"


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


class TestCompareWithBaseline:
    """A device that rewrote its save without changing it must not conflict."""

    SYNCED = datetime(2026, 1, 5, tzinfo=timezone.utc)

    def test_unchanged_client_against_a_changed_server_downloads(self):
        result = compare_save_state(
            client_hash="client_hash",
            client_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            server_hash="server_new",
            server_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            device_last_synced_at=self.SYNCED,
            device_last_sync_hash="client_hash",
            device_last_sync_server_hash="server_old",
        )
        assert result.action == "download"
        assert result.reason == "Server save is newer than last sync"

    def test_matching_baselines_return_no_op(self):
        result = compare_save_state(
            client_hash="client_hash",
            client_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            server_hash="server_hash",
            server_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            device_last_synced_at=self.SYNCED,
            device_last_sync_hash="client_hash",
            device_last_sync_server_hash="server_hash",
        )
        assert result.action == "no_op"
        assert result.reason == "No changes since last sync"

    def test_without_a_client_baseline_the_same_inputs_conflict(self):
        """The back-compat guard: no baseline keeps today's timestamp behaviour."""
        result = compare_save_state(
            client_hash="client_hash",
            client_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            server_hash="server_new",
            server_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            device_last_synced_at=self.SYNCED,
            device_last_sync_server_hash="server_old",
        )
        assert result.action == "conflict"
        assert result.reason == "Both sides changed since last sync"

    def test_unchanged_server_against_a_changed_client_returns_no_op(self):
        result = compare_save_state(
            client_hash="client_new",
            client_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            server_hash="server_hash",
            server_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            device_last_synced_at=self.SYNCED,
            device_last_sync_server_hash="server_hash",
        )
        assert result.action == "no_op"
        assert result.reason == "No changes since last sync"

    def test_a_client_baseline_mismatch_is_not_evidence_of_change(self):
        result = compare_save_state(
            client_hash="client_new",
            client_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            server_hash="server_hash",
            server_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            device_last_synced_at=self.SYNCED,
            device_last_sync_hash="client_old",
        )
        assert result.action == "no_op"

    def test_empty_hashes_never_match(self):
        result = compare_save_state(
            client_hash="",
            client_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            server_hash="",
            server_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            device_last_synced_at=self.SYNCED,
            device_last_sync_hash="",
            device_last_sync_server_hash="",
        )
        assert result.action == "upload"
        assert result.reason == "Client save is newer than last sync"

    def test_a_baseline_without_sync_history_decides_a_newer_client(self):
        """A baseline is only ever written with a boundary, so it cannot act alone."""
        result = compare_save_state(
            client_hash="client_hash",
            client_updated_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            server_hash="server_hash",
            server_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            device_last_synced_at=None,
            device_last_sync_hash="client_hash",
            device_last_sync_server_hash="server_hash",
        )
        assert result.action == "upload"
        assert result.reason == "Client save is newer (no sync history)"

    def test_a_baseline_without_sync_history_decides_equal_timestamps(self):
        ts = datetime(2026, 1, 5, tzinfo=timezone.utc)
        result = compare_save_state(
            client_hash="client_hash",
            client_updated_at=ts,
            server_hash="server_hash",
            server_updated_at=ts,
            device_last_synced_at=None,
            device_last_sync_hash="client_hash",
            device_last_sync_server_hash="server_hash",
        )
        assert result.action == "conflict"
        assert result.reason == "Same timestamp but different content"


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
