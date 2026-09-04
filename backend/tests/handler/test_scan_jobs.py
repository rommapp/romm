from datetime import datetime, timezone

from rq.job import JobStatus
from tests.scan_job_stubs import (
    NON_SCAN_FUNC,
    make_job,
    make_scoped_job,
    make_task_job,
    patch_scan_jobs,
)

import handler.scan_jobs as scan_jobs
from endpoints.sockets.scan import scan_platforms
from handler.scan_jobs import SCAN_PLATFORMS_FUNC


def test_the_scan_func_name_matches_the_function():
    """The constant stands in for an import the other direction, so it has to
    keep naming the function RQ actually records."""
    assert scan_jobs.SCAN_PLATFORMS_FUNC == (
        f"{scan_platforms.__module__}.{scan_platforms.__name__}"
    )


class TestIsScanJob:
    def test_recognises_a_directly_enqueued_scan(self):
        assert scan_jobs.is_scan_job(make_job(SCAN_PLATFORMS_FUNC))

    def test_recognises_a_scan_that_runs_through_the_task_runner(self):
        assert scan_jobs.is_scan_job(make_task_job())

    def test_ignores_another_task(self):
        assert not scan_jobs.is_scan_job(make_job(NON_SCAN_FUNC))


class TestIsScopedScanJob:
    def test_recognises_a_scan_of_named_roms(self):
        assert scan_jobs.is_scoped_scan_job(make_scoped_job())

    def test_treats_a_library_scan_as_unscoped(self):
        assert not scan_jobs.is_scoped_scan_job(make_job(SCAN_PLATFORMS_FUNC))

    def test_treats_a_scan_it_cannot_read_as_unscoped(self, mocker):
        # A payload that will not deserialize fails on the next dequeue, so it
        # stops standing in the way by itself.
        mocker.patch.object(scan_jobs, "get_job_kwargs", return_value=None)

        assert not scan_jobs.is_scoped_scan_job(make_scoped_job())


class TestGetQueuedScanJobs:
    def test_collects_scans_from_every_queue(self, mocker):
        # A scan enqueued by an older release sits on one of the other queues,
        # where a worker will still run it.
        scan = make_job(SCAN_PLATFORMS_FUNC)
        high = make_job(SCAN_PLATFORMS_FUNC)
        low = make_task_job()
        patch_scan_jobs(
            mocker, scan_queued=[scan], high_queued=[high], low_queued=[low]
        )

        assert scan_jobs.get_queued_scan_jobs() == [scan, high, low]

    def test_leaves_out_jobs_that_are_not_scans(self, mocker):
        patch_scan_jobs(mocker, high_queued=[make_job(NON_SCAN_FUNC)])

        assert scan_jobs.get_queued_scan_jobs() == []

    def test_leaves_out_a_scan_that_is_no_longer_queued(self, mocker):
        job = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.STARTED)
        patch_scan_jobs(mocker, high_queued=[job])

        assert scan_jobs.get_queued_scan_jobs() == []


class TestGetRunningScanJob:
    def test_returns_the_scan_a_worker_is_holding(self, mocker):
        job = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.STARTED)
        patch_scan_jobs(mocker, running=job)

        assert scan_jobs.get_running_scan_job() is job

    def test_returns_none_when_a_worker_outlived_its_job(self, mocker):
        patch_scan_jobs(mocker, worker_lost=True)

        assert scan_jobs.get_running_scan_job() is None


class TestGetBlockingLibraryScans:
    """Only a library scan makes another one wait."""

    def test_reports_the_library_scans_in_flight(self, mocker):
        running = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.STARTED)
        queued = make_job(SCAN_PLATFORMS_FUNC)
        patch_scan_jobs(mocker, running=running, scan_queued=[queued])

        assert scan_jobs.get_blocking_library_scans() == (running, [queued])

    def test_a_scan_of_named_roms_blocks_nothing(self, mocker):
        # It resolves its work from the database and is done in seconds.
        patch_scan_jobs(
            mocker, running=make_scoped_job(), scan_queued=[make_scoped_job()]
        )

        assert scan_jobs.get_blocking_library_scans() == (None, [])


class TestGetPendingScanJobs:
    def test_counts_queued_and_delayed_scans_but_not_running_ones(self, mocker):
        queued = make_job(SCAN_PLATFORMS_FUNC)
        delayed = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.SCHEDULED)
        running = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.STARTED)
        patch_scan_jobs(
            mocker, running=running, high_queued=[queued], scheduled=[delayed]
        )

        assert scan_jobs.get_pending_scan_jobs() == [queued, delayed]


class TestDropStaleScheduledScans:
    """A worker that starts after downtime must not release a backlog."""

    def test_drops_a_scan_long_past_due(self, mocker):
        job = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.SCHEDULED)
        registry = patch_scan_jobs(mocker, scheduled=[job])
        registry.get_jobs_to_schedule.return_value = [job.id]

        assert scan_jobs.drop_stale_scheduled_scans() == 1
        job.cancel.assert_called_once()

    def test_asks_the_registry_only_for_what_is_past_due(self, mocker):
        registry = patch_scan_jobs(mocker)

        scan_jobs.drop_stale_scheduled_scans()

        cutoff = registry.get_jobs_to_schedule.call_args.args[0]
        expected = datetime.now(timezone.utc) - scan_jobs.STALE_SCHEDULED_SCAN_AGE
        assert abs(cutoff - expected.timestamp()) < 5

    def test_keeps_a_scan_still_waiting_out_its_delay(self, mocker):
        job = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.SCHEDULED)
        patch_scan_jobs(mocker, scheduled=[job])

        assert scan_jobs.drop_stale_scheduled_scans() == 0
        job.cancel.assert_not_called()

    def test_ignores_a_scan_that_left_the_registry(self, mocker):
        job = make_job(SCAN_PLATFORMS_FUNC, status=JobStatus.SCHEDULED)
        registry = patch_scan_jobs(mocker)
        registry.get_jobs_to_schedule.return_value = [job.id]

        assert scan_jobs.drop_stale_scheduled_scans() == 0
        job.cancel.assert_not_called()

    def test_leaves_jobs_that_are_not_scans_alone(self, mocker):
        job = make_job(NON_SCAN_FUNC, status=JobStatus.SCHEDULED)
        registry = patch_scan_jobs(mocker, scheduled=[job])
        registry.get_jobs_to_schedule.return_value = [job.id]

        assert scan_jobs.drop_stale_scheduled_scans() == 0
        job.cancel.assert_not_called()


class TestScheduledScanRegistries:
    """A scan delayed by an older release is still in the low priority queue."""

    def test_reads_the_scan_queue_and_the_low_queue(self):
        names = [registry.name for registry in scan_jobs._scheduled_scan_registries()]

        assert names == [scan_jobs.scan_queue.name, scan_jobs.low_prio_queue.name]
